# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Local Python/FastAPI application with plain HTML/CSS/JavaScript, SQLite, OpenCV and yt-dlp. Implementation choice for the authorized MVP; local versus shared deployment was asked as an optional preference and remains open.

## Users

FRC scouts and analysts reviewing robot performance from recorded matches.

## Product Purpose

Produce reviewable video-derived scouting observations and compare aggregate observations against The Blue Alliance scoring data. Initial dataset: team 8324 in 2026, as requested.

## Capabilities and Constraints

Match and video discovery, local footage, automated fuel-entry proposals, human correction and attribution, official-result context, CSV/JSON exports. Computer-vision proposals are not validated makes. Team-specific statistics require reviewed attribution. Missing data remains unknown.

## Operating Context

Assumption for this MVP: one reviewer runs the application locally, with local footage and no hosted deployment. Desktop is primary; narrow screens must remain usable. No user-specific accessibility requirements supplied.

## Evidence on Hand

Research pack in docs/research; 25 real 2026 matches for team 8324 from TBA. API key absent; public TBA pages provide explicitly labeled fallback data. Footage is being downloaded from video links attached to those matches.

GPU ML requirement: Primary video analysis must use trained object detection on CUDA without requiring manual ROI or labels. Implemented with frc9550 YOLO26n; detecting fuel does not establish made-shot counts or robot attribution.

Unattended requirement: The user opens a dashboard and reads automatic estimates; no button or manual labels are required to start analysis. Every decoded frame should receive fuel inference, robot positions should be tracked, fuel-counter deltas should reconcile volleys, and each match has a two-hour processing deadline. Experimental estimates, raw counts, official data, and unknown robot contributions must be distinguishable.
