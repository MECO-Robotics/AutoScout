"""Fetch pinned public fuel weights and retain their upstream license and card."""
import hashlib
from pathlib import Path
import urllib.request

root=Path(__file__).resolve().parents[1]/'data/models/frc9550'
root.mkdir(parents=True,exist_ok=True)
base='https://huggingface.co/frc9550/2026-game-piece/resolve/da2f9c9b3fad702c4b6579a5a4d5d4d4f3fddf42/'
expected='6de918b938c5e0603eb49742b3c2ad523aa0e0ab7907d4918366e736d5f870eb'
for name in ('model.pt','LICENSE','README.md'):
    with urllib.request.urlopen(base+name,timeout=60) as response:
        data=response.read()
    if name=='model.pt' and hashlib.sha256(data).hexdigest()!=expected:
        raise ValueError('Model checksum does not match the pinned artifact.')
    temporary=root/(name+'.part');temporary.write_bytes(data);temporary.replace(root/name)
print(root/'model.pt')

robot_url='https://raw.githubusercontent.com/ai4funhobby-oss/RobotTracking/b1af3ef2811f59c25e3908cc96720707e055e66e/runs/detect/robot_detector3/weights/best.pt'
with urllib.request.urlopen(robot_url,timeout=60) as response:
    robot_data=response.read()
if hashlib.sha256(robot_data).hexdigest()!='e43d481d67f19b1737e7d28074f6609feba4e587a7eac921e8372b375ae40dae':
    raise ValueError('Robot model checksum mismatch')
robot_dir=root.parent/'robots';robot_dir.mkdir(exist_ok=True)
part=robot_dir/'robottracking.pt.part';part.write_bytes(robot_data);part.replace(robot_dir/'robottracking.pt')
print(robot_dir/'robottracking.pt')
