"""Short image-space flight evidence, not a guarantee of a made basket.

Coordinates are normalized broadcast coordinates. A quadratic fit is local to a
camera segment; it is deliberately not a ground-plane homography for airborne fuel.
"""
from collections import Counter, deque

import numpy as np
from scipy.spatial import cKDTree

from .scoring import identity


class FlightTracker:
    def __init__(self, gap=.12, max_flight=3.0):
        self.gap = gap
        self.max_flight = max_flight
        self.tracks = {}
        self.next_id = 1
        self.segment = None
        self.robots = deque()
        self.diagnostics = Counter()

    def _fit(self, history):
        if len(history) < 5 or history[-1][0] - history[0][0] < .06:
            return None
        data = np.asarray(history, dtype=float)
        times = data[:, 0] - data[-1, 0]
        design = np.column_stack((np.ones(len(times)), times, times * times))
        coefficients = np.linalg.lstsq(design, data[:, 1:], rcond=None)[0]
        residual = float(np.sqrt(np.mean(np.sum((design @ coefficients - data[:, 1:]) ** 2, axis=1))))
        return coefficients, residual

    def _source(self, track):
        """Look backward at robot boxes at launch, never at entry-time positions."""
        history = track['flight_history']
        start, x, y = history[0]
        origin = np.array([x, y])
        departure = np.array(history[min(3, len(history)-1)][1:])
        candidates = {}
        for when, robots in self.robots:
            if abs(when - start) > .12:
                continue
            for tid, box, team in robots:
                x1, y1, x2, y2 = box
                width, height = max(x2-x1, .005), max(y2-y1, .005)
                # A bumper detector needs robot-relative room for the shooter above it.
                if not (x1-.25*width <= x <= x2+.25*width and y1-1.8*height <= y <= y2):
                    continue
                center = np.array([(x1+x2)/2, (y1+y2)/2])
                if np.linalg.norm(departure-center) <= np.linalg.norm(origin-center):
                    continue
                candidates[tid] = team
        if len(candidates) != 1:
            self.diagnostics['ambiguous_launch' if candidates else 'unresolved_launch'] += 1
            return None, None
        return next(iter(candidates.items()))

    def update(self, boxes, timestamp, robots, hubs, camera_segment=0):
        if camera_segment != self.segment:
            self.tracks.clear()
            self.robots.clear()
            self.segment = camera_segment
        self.robots.append((timestamp, [(tid, tuple(r['box']), identity(r)) for tid, r in robots]))
        while self.robots and timestamp-self.robots[0][0] > self.max_flight+.3:
            self.robots.popleft()
        self.tracks = {tid:t for tid,t in self.tracks.items() if 0 <= timestamp-t['time'] <= self.gap}
        centers = np.asarray([[(b[0]+b[2])/2, (b[1]+b[3])/2] for b in boxes], dtype=float).reshape(-1,2)
        assignments = {}
        if len(centers) and self.tracks:
            tree = cKDTree(centers)
            pairs = []
            for tid, track in self.tracks.items():
                dt = timestamp-track['time']
                prediction = track['point']+track['velocity']*dt
                fit = track.get('fit')
                if fit is not None and fit[1] < .008:
                    prediction = np.array([1, dt, dt*dt]) @ fit[0]
                size = max(track['box'][2]-track['box'][0], track['box'][3]-track['box'][1])
                radius = min(.045, max(.007, size*1.5)+dt*.15)
                for j in tree.query_ball_point(prediction, radius):
                    pairs.append((float(np.linalg.norm(centers[j]-prediction)),tid,j))
            used = set()
            for distance,tid,j in sorted(pairs):
                if tid not in used and j not in assignments:
                    assignments[j] = tid
                    used.add(tid)
        output, crossings = [], []
        for j, center in enumerate(centers):
            tid = assignments.get(j)
            if tid is None:
                tid = self.next_id
                self.next_id += 1
                self.tracks[tid] = {'point':center, 'velocity':np.zeros(2), 'time':timestamp,
                                    'history':[], 'flight_history':[], 'votes':Counter(),
                                    'scored':False, 'stale':False, 'fit':None}
            track = self.tracks[tid]
            dt = timestamp-track['time']
            if dt > 0:
                track['velocity'] = .3*track['velocity']+.7*(center-track['point'])/dt
            track.update(point=center, time=timestamp, box=boxes[j])
            track['history'].append((timestamp,*center))
            track['history'] = [h for h in track['history'] if timestamp-h[0] <= .15]
            recent = track['history']
            moving = len(recent)>=3 and np.linalg.norm(center-np.asarray(recent[0][1:])) > .006
            if not track['flight_history'] and moving:
                track['flight_history'] = list(recent)
            elif track['flight_history']:
                track['flight_history'].append((timestamp,*center))
            flight = track['flight_history']
            if flight and timestamp-flight[0][0] > self.max_flight:
                if not track['stale']:
                    self.diagnostics['stale_flight_rejected'] += 1
                track['stale'] = True
                track['fit'] = None
                track['flight_history'] = flight[-2:]
            # Once stale, never relatch the same continuously associated object.
            # A lost track will naturally expire, permitting a new physical flight.
            if flight and not track['stale'] and not track['scored']:
                track['fit'] = self._fit(flight[-30:])
                if len(flight)>=5 and track['fit'] is not None:
                    coefficients, residual = track['fit']
                    size = max(boxes[j][2]-boxes[j][0], boxes[j][3]-boxes[j][1])
                    if residual <= max(.003, min(.012, size)):
                        for alliance, gate in hubs.items():
                            prev = flight[-2]
                            if not (0 < timestamp-prev[0] <= self.gap and prev[2] < gate['y'] <= center[1]
                                    and flight[-3][2] < gate['y'] and track['velocity'][1] > .03):
                                continue
                            alpha = (gate['y']-prev[2])/(center[1]-prev[2])
                            entry_x = prev[1]+alpha*(center[0]-prev[1])
                            if not gate['left'] <= entry_x <= gate['right']:
                                continue
                            full_fit = self._fit(flight)
                            if full_fit is None or full_fit[1] > max(.006, min(.02, 2*size)):
                                self.diagnostics['inconsistent_flight_rejected'] += 1
                                continue
                            source, team = self._source(track)
                            launch = flight[0][0]
                            track.update(scored=True, source_track=source, launch_timestamp=launch, fit=None)
                            crossings.append({'timestamp':timestamp, 'alliance':alliance, 'ball_track':tid,
                                              'robot_track':source, 'team':team, 'launch_timestamp':launch,
                                              'flight_seconds':timestamp-launch, 'camera_segment':camera_segment,
                                              'trajectory':{'samples':len(flight), 'fit_residual':residual,
                                                            'full_flight_residual':full_fit[1], 'points':[list(point) for point in flight],
                                                            'start':list(flight[0]), 'entry':[timestamp,float(entry_x),gate['y']],
                                                            'method':'short image-space quadratic; timestamped launch association'},
                                              'confidence':'experimental crossing candidate'})
                            break
            output.append((tid,track))
        return output,crossings
