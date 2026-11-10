"""A Human-1M-style view of the egocentric data (DA-04, Hiếu 11/11/2026).

The team's tray recordings and the EgoDex sample, after `fw egocentric` de-identified,
posed and checked them, become LeRobot v3.0 shards laid out like NVIDIA's Human-1M
release (per-frame 21-joint hands in the camera frame, masks and confidence, camera
pose; per-episode intrinsics and anonymous ids; task, subtask, environment and scene
dictionaries), plus a static explorer page. Only the structure follows Human-1M; no
code, text or artwork of it is copied. A field a source does not have stays empty
(NaN or null) and `info.json` says why, as Human-1M does.

    layout    joint order, bones, feature table, path templates
    frames    per-frame hand and camera arrays of one episode, from E-A or E-B
    subtasks  timed, hand-specific subtask annotations
    quality   Human-1M episode requirements, measured
    video     the ffmpeg encoder (H.264 mp4), behind a Protocol
    writer    one LeRobot v3.0 shard
    check     schema check of a written shard
    build     work directories -> status table, shards, explorer
    viewer    the static explorer (HTML + three.js, no server)
"""
