#!/usr/bin/env python3
"""
MonarchVoice Audiobook Compiler Workflow
Strips ID3v1/ID3v2 tags and LAME Info/Xing headers from individual Law MP3 episodes
and merges them into seamless Volume and Master Audiobook MP3 files.
"""
import glob
import os

def strip_id3_and_info(data: bytes) -> bytes:
    pos = 0
    if data[:3] == b'ID3':
        size = ((data[6] & 0x7f) << 21) | ((data[7] & 0x7f) << 14) | ((data[8] & 0x7f) << 7) | (data[9] & 0x7f)
        pos = 10 + size
    while pos < len(data) - 4:
        if data[pos] == 0xFF and (data[pos+1] & 0xE0) == 0xE0:
            break
        pos += 1
    if b'Info' in data[pos:pos+300] or b'Xing' in data[pos:pos+300]:
        p2 = pos + 4
        while p2 < len(data) - 4:
            if data[p2] == 0xFF and (data[p2+1] & 0xE0) == 0xE0 and data[p2:p2+2] == data[pos:pos+2]:
                pos = p2
                break
            p2 += 1
    end = len(data)
    if end >= 128 and data[end-128:end-125] == b'TAG':
        end -= 128
    return data[pos:end]

def main():
    files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), 'deep_audio', 'Law_*.mp3')))
    master = bytearray()
    for f in files:
        with open(f, 'rb') as fp:
            master.extend(strip_id3_and_info(fp.read()))
    out_path = os.path.join(os.path.dirname(__file__), 'The_48_Laws_of_Power_Master_Deep_Audiobook.mp3')
    with open(out_path, 'wb') as fp:
        fp.write(master)
    print(f"Compiled {len(files)} episodes -> {out_path} ({len(master):,} bytes)")

if __name__ == '__main__':
    main()
