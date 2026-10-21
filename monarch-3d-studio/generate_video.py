#!/usr/bin/env python3
import cv2
import numpy as np
import math, random
from pathlib import Path

# Config
W, H = 1280, 720  # 16:9
FPS = 30
DURATION = 20
TOTAL_FRAMES = DURATION * FPS
OUTPUT = Path(__file__).parent / "MonarchVoice-3D-Stickman-20s-16x9.mp4"

# Colors BGR (opencv)
BG_DARK = (14, 12, 8)      # #080c0e approx but BGR
BG_MID = (31, 15, 10)
BG_LIGHT = (45, 24, 10)
GOLD = (0, 215, 255)       # #FFD700 -> BGR
GOLD_DARK = (0, 140, 255)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (42, 42, 255)
RED_DARK = (20, 20, 120)
CYAN = (255, 230, 0)
DARK_BLUE = (42, 22, 14)
NEON_GOLD = (0, 215, 255)
NEON_CYAN = (255, 240, 100)

# Pre-generate city buildings
random.seed(0)
buildings = []
# far city skyline
for i in range(25):
    x = random.randint(-200, W+200)
    w = random.randint(60, 140)
    h = random.randint(80, 280)
    col = random.choice([(22,16,8), (26,18,12), (18,22,30), (20,20,28)])
    emissive = random.random() > 0.5
    buildings.append((x, w, h, col, emissive))

particles = []
for i in range(100):
    particles.append({
        'x': random.randint(0, W),
        'y': random.randint(0, H),
        'r': random.uniform(0.8, 2.2),
        'vx': random.uniform(-0.4, 0.4),
        'vy': random.uniform(-0.6, -0.1),
        'alpha': random.uniform(0.3, 0.8)
    })

def lerp(a,b,t): return a + (b-a)*t
def ease_in_out(t): return 2*t*t if t<0.5 else -1+(4-2*t)*t
def clamp(v,a,b): return max(a, min(b, v))

def draw_gradient_bg(img, t):
    # vertical gradient dark to mid
    for y in range(H):
        ratio = y / H
        # subtle animated shift
        r = int( lerp(5, 12, ratio) + math.sin(t*0.3)*1 )
        g = int( lerp(8, 18, ratio) )
        b = int( lerp(16, 26, ratio) )
        cv2.line(img, (0,y), (W,y), (b,g,r), 1)
    # vignette
    # create radial vignette overlay
    vignette = np.zeros((H,W,3), dtype=np.uint8)
    cx, cy = W//2, H//2
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            dx = (x - cx)/ (W/2)
            dy = (y - cy)/ (H/2)
            d = math.sqrt(dx*dx + dy*dy) * 0.6
            d = clamp(d, 0, 1)
            dark = int(d*90)
            if dark>0:
                cv2.rectangle(vignette, (x,y), (x+2,y+2), (dark,dark,dark), -1)
    img[:] = cv2.subtract(img, vignette//3)

def draw_city(img, t):
    # horizon line
    horizon_y = int(H*0.55)
    # buildings
    cam_offset = math.sin(t*0.2)*8  # subtle camera drift
    for (x,w,h,col,emissive) in buildings:
        bx = int(x + cam_offset)
        by = horizon_y
        # only draw if in view
        if bx+w < -100 or bx > W+100: continue
        # building body
        top = by - h
        cv2.rectangle(img, (bx, top), (bx+w, by), col, -1)
        # windows
        if emissive:
            win_col = (90, 160, 255) if random.random()>0.5 else (180, 210, 255)
            # draw 3x4 windows
            for wy in range(3):
                for wx in range(2):
                    wx0 = bx + 12 + wx*(w-24)//2
                    wy0 = top + 18 + wy*(h-40)//3
                    wx1 = wx0 + (w-30)//2
                    wy1 = wy0 + 12
                    # flicker
                    alpha = 0.25 + 0.15*math.sin(t*2 + bx*0.01)
                    if ((bx+wy)%3==0):
                        cv2.rectangle(img, (wx0,wy0),(wx1,wy1), win_col, -1)
                        # glow
                        cv2.rectangle(img, (wx0,wy0),(wx1,wy1), (40,40,40), 1)
        # outline
        cv2.rectangle(img, (bx, top),(bx+w, by), (30,30,40), 1)
    # horizon glow
    cv2.line(img, (0, horizon_y), (W, horizon_y), (35, 35, 55), 2)

def draw_grid_floor(img, t):
    # perspective grid on ground (below horizon)
    horizon_y = int(H*0.55)
    ground_y0 = horizon_y
    ground_y1 = H
    # draw horizontal lines with perspective
    for i in range(12):
        y = int( lerp(ground_y0, ground_y1, (i/12)**1.3) )
        alpha = int( lerp(30, 15, i/12) )
        cv2.line(img, (0,y), (W,y), (alpha, alpha, alpha+10), 1)
    # vertical perspective lines
    cx = W//2 + int(math.sin(t*0.15)*18)
    for i in range(-6, 7):
        x_center = cx + i*90
        # converge to center
        # bottom x spread wider
        # top converges to center
        x_top = cx + i*20
        x_bottom = cx + i*180
        cv2.line(img, (x_top, ground_y0), (x_bottom, ground_y1), (28,28,38), 1)
    # neon lines
    neon_y1 = int( lerp(ground_y0, ground_y1, 0.42) )
    neon_y2 = neon_y1 + 8
    # gold line
    cv2.line(img, (0, neon_y1), (W, neon_y1), GOLD, 2)
    # cyan line slightly offset
    cv2.line(img, (0, neon_y2), (W, neon_y2), (255,220,0), 1)
    # glow under lines
    overlay = img.copy()
    cv2.line(overlay, (0, neon_y1), (W, neon_y1), (20, 180, 255), 6)
    cv2.line(overlay, (0, neon_y2), (W, neon_y2), (100, 200, 255), 4)
    img[:] = cv2.addWeighted(img, 1.0, overlay, 0.18, 0)

def draw_particles(img, t):
    for p in particles:
        x = p['x'] + p['vx']*t*25
        y = p['y'] + p['vy']*t*25 + math.sin(t*0.8 + p['x']*0.01)*2
        # wrap
        x = x % (W+40) - 20
        y = y % (H+40) - 20
        r = int(p['r']* (1 + 0.3*math.sin(t*2 + p['x']*0.02)))
        alpha = p['alpha'] * (0.7 + 0.3*math.sin(t*1.5 + p['y']*0.01))
        col = (int(200*alpha), int(215*alpha), int(255*alpha))
        cv2.circle(img, (int(x), int(y)), r, col, -1)
        # glow
        if r>1:
            cv2.circle(img, (int(x), int(y)), r+1, (30,30,60), 1)

def draw_beams(img, t):
    # vertical light beams in city
    horizon_y = int(H*0.55)
    beam_xs = [W*0.22, W*0.48, W*0.74, W*0.88]
    for i, bx in enumerate(beam_xs):
        bx = int(bx + math.sin(t*0.2+i)*6)
        top = horizon_y - 260 - int(20*math.sin(t*0.5+i))
        bottom = horizon_y
        # beam as transparent gradient polygon
        overlay = img.copy()
        pts = np.array([[bx-18, bottom],[bx+18, bottom],[bx+6, top],[bx-6, top]], np.int32)
        cv2.fillPoly(overlay, [pts], (255, 240, 180))
        alpha = 0.04 + 0.02*math.sin(t*1.2+i)
        img[:] = cv2.addWeighted(img, 1.0, overlay, alpha, 0)

def draw_stickman(img, cx, cy, scale, pose, t, is_hero, phase_t=0):
    """
    cx, cy = foot center (bottom)
    scale: 1.0 = normal
    pose: 'idle','ready','punch','hit','victory','down'
    """
    s = scale
    # head
    head_r = int(22*s)
    head_cx = int(cx)
    head_cy = int(cy - 108*s)
    # torso top/base
    torso_top_y = head_cy + int(18*s)
    torso_bot_y = torso_top_y + int(42*s)
    torso_x = cx
    torso_w = int(18*s)

    # shadow under feet
    shadow_w = int(42*s)
    shadow_h = int(10*s)
    cv2.ellipse(img, (int(cx), int(cy+6)), (shadow_w, shadow_h), 0,0,360, (0,0,0), -1)
    # soften shadow via overlay
    # outline shadow fade
    # draw legs
    hip_y = torso_bot_y + int(4*s)
    hip_x_left = int(cx - 10*s)
    hip_x_right = int(cx + 10*s)
    knee_y = hip_y + int(34*s)
    foot_y = knee_y + int(32*s)

    # leg animation based on pose
    if pose == 'idle':
        walk = math.sin(t*4)
        # left leg swing
        left_knee_offset = int(walk*10*s)
        right_knee_offset = int(-walk*10*s)
        # arms
        left_arm_swing = walk*0.22
        right_arm_swing = -walk*0.22
        # draw legs simple
        # left leg
        left_knee_x = hip_x_left + left_knee_offset//3
        right_knee_x = hip_x_right + right_knee_offset//3
        left_foot_x = left_knee_x + left_knee_offset//2
        right_foot_x = right_knee_x + right_knee_offset//2
        # torso lines
        cv2.line(img, (torso_x, torso_top_y), (torso_x, hip_y), WHITE, int(10*s))
        # arms
        shoulder_y = torso_top_y + int(12*s)
        shoulder_lx = int(torso_x - torso_w//2)
        shoulder_rx = int(torso_x + torso_w//2)
        # left arm
        elbow_lx = int(shoulder_lx - 6*s + left_arm_swing*22)
        elbow_ly = int(shoulder_y + 22*s)
        hand_lx = int(elbow_lx - 2*s + left_arm_swing*12)
        hand_ly = int(elbow_ly + 22*s)
        cv2.line(img, (shoulder_lx, shoulder_y), (elbow_lx, elbow_ly), WHITE, int(7*s))
        cv2.line(img, (elbow_lx, elbow_ly), (hand_lx, hand_ly), WHITE, int(6*s))
        cv2.circle(img, (shoulder_lx, shoulder_y), int(6*s), GOLD, -1)
        cv2.circle(img, (elbow_lx, elbow_ly), int(5*s), GOLD, -1)
        cv2.circle(img, (hand_lx, hand_ly), int(4*s), WHITE, -1)
        # right arm
        elbow_rx = int(shoulder_rx + 6*s + right_arm_swing*22)
        elbow_ry = int(shoulder_y + 22*s)
        hand_rx = int(elbow_rx + 2*s + right_arm_swing*12)
        hand_ry = int(elbow_ry + 22*s)
        cv2.line(img, (shoulder_rx, shoulder_y), (elbow_rx, elbow_ry), WHITE, int(7*s))
        cv2.line(img, (elbow_rx, elbow_ry), (hand_rx, hand_ry), WHITE, int(6*s))
        cv2.circle(img, (shoulder_rx, shoulder_y), int(6*s), GOLD, -1)
        cv2.circle(img, (elbow_rx, elbow_ry), int(5*s), GOLD, -1)
        cv2.circle(img, (hand_rx, hand_ry), int(4*s), WHITE, -1)

        # legs
        cv2.line(img, (hip_x_left, hip_y), (left_knee_x, knee_y), WHITE, int(8*s))
        cv2.line(img, (left_knee_x, knee_y), (left_foot_x, foot_y), WHITE, int(7*s))
        cv2.circle(img, (hip_x_left, hip_y), int(6*s), GOLD, -1)
        cv2.circle(img, (left_knee_x, knee_y), int(5*s), GOLD, -1)
        cv2.circle(img, (left_foot_x, foot_y), int(5*s), WHITE, -1)

        cv2.line(img, (hip_x_right, hip_y), (right_knee_x, knee_y), WHITE, int(8*s))
        cv2.line(img, (right_knee_x, knee_y), (right_foot_x, foot_y), WHITE, int(7*s))
        cv2.circle(img, (hip_x_right, hip_y), int(6*s), GOLD, -1)
        cv2.circle(img, (right_knee_x, knee_y), int(5*s), GOLD, -1)
        cv2.circle(img, (right_foot_x, foot_y), int(5*s), WHITE, -1)

    elif pose == 'ready':
        # guard stance - fists up
        cv2.line(img, (torso_x, torso_top_y), (torso_x, hip_y), WHITE, int(10*s))
        shoulder_y = torso_top_y + int(12*s)
        shoulder_lx = int(torso_x - torso_w//2)
        shoulder_rx = int(torso_x + torso_w//2)
        # left guard
        elbow_lx = int(shoulder_lx - 2*s)
        elbow_ly = int(shoulder_y + 8*s)
        hand_lx = int(elbow_lx + 16*s)
        hand_ly = int(shoulder_y - 6*s)
        cv2.line(img, (shoulder_lx, shoulder_y), (elbow_lx, elbow_ly), WHITE, int(7*s))
        cv2.line(img, (elbow_lx, elbow_ly), (hand_lx, hand_ly), WHITE, int(6*s))
        cv2.circle(img, (shoulder_lx, shoulder_y), int(6*s), GOLD, -1)
        cv2.circle(img, (elbow_lx, elbow_ly), int(5*s), GOLD, -1)
        cv2.circle(img, (hand_lx, hand_ly), int(6*s), WHITE, -1)
        # right guard
        elbow_rx = int(shoulder_rx + 2*s)
        elbow_ry = int(shoulder_y + 8*s)
        hand_rx = int(elbow_rx - 16*s)
        hand_ry = int(shoulder_y - 6*s)
        cv2.line(img, (shoulder_rx, shoulder_y), (elbow_rx, elbow_ry), WHITE, int(7*s))
        cv2.line(img, (elbow_rx, elbow_ry), (hand_rx, hand_ry), WHITE, int(6*s))
        cv2.circle(img, (shoulder_rx, shoulder_y), int(6*s), GOLD, -1)
        cv2.circle(img, (elbow_rx, elbow_ry), int(5*s), GOLD, -1)
        cv2.circle(img, (hand_rx, hand_ry), int(6*s), WHITE, -1)
        # legs - slightly bent, wide
        left_knee_x = hip_x_left - int(6*s)
        right_knee_x = hip_x_right + int(6*s)
        left_foot_x = left_knee_x - int(4*s)
        right_foot_x = right_knee_x + int(4*s)
        cv2.line(img, (hip_x_left, hip_y), (left_knee_x, knee_y), WHITE, int(8*s))
        cv2.line(img, (left_knee_x, knee_y), (left_foot_x, foot_y), WHITE, int(7*s))
        cv2.circle(img, (hip_x_left, hip_y), int(6*s), GOLD, -1)
        cv2.circle(img, (left_knee_x, knee_y), int(5*s), GOLD, -1)
        cv2.circle(img, (left_foot_x, foot_y), int(5*s), WHITE, -1)
        cv2.line(img, (hip_x_right, hip_y), (right_knee_x, knee_y), WHITE, int(8*s))
        cv2.line(img, (right_knee_x, knee_y), (right_foot_x, foot_y), WHITE, int(7*s))
        cv2.circle(img, (hip_x_right, hip_y), int(6*s), GOLD, -1)
        cv2.circle(img, (right_knee_x, knee_y), int(5*s), GOLD, -1)
        cv2.circle(img, (right_foot_x, foot_y), int(5*s), WHITE, -1)

    elif pose == 'punch':
        # right arm extended
        # phase_t 0..1 => punch extent
        punch_ext = math.sin(phase_t * math.pi) # 0->1->0
        # left guard still
        cv2.line(img, (torso_x, torso_top_y), (torso_x, hip_y), WHITE, int(10*s))
        shoulder_y = torso_top_y + int(12*s)
        shoulder_lx = int(torso_x - torso_w//2)
        shoulder_rx = int(torso_x + torso_w//2)
        # left guard
        elbow_lx = int(shoulder_lx - 2*s)
        elbow_ly = int(shoulder_y + 8*s)
        hand_lx = int(elbow_lx + 16*s)
        hand_ly = int(shoulder_y - 6*s)
        cv2.line(img, (shoulder_lx, shoulder_y), (elbow_lx, elbow_ly), WHITE, int(7*s))
        cv2.line(img, (elbow_lx, elbow_ly), (hand_lx, hand_ly), WHITE, int(6*s))
        cv2.circle(img, (shoulder_lx, shoulder_y), int(6*s), GOLD, -1)
        cv2.circle(img, (elbow_lx, elbow_ly), int(5*s), GOLD, -1)
        cv2.circle(img, (hand_lx, hand_ly), int(6*s), WHITE, -1)
        # right punch
        # elbow moves forward
        elbow_rx = int(shoulder_rx + 14*s + punch_ext*22*s)
        elbow_ry = int(shoulder_y + 6*s)
        hand_rx = int(elbow_rx + 18*s + punch_ext*26*s)
        hand_ry = int(elbow_ry + int(punch_ext*4*s))
        cv2.line(img, (shoulder_rx, shoulder_y), (elbow_rx, elbow_ry), WHITE, int(7*s))
        cv2.line(img, (elbow_rx, elbow_ry), (hand_rx, hand_ry), WHITE, int(6*s))
        cv2.circle(img, (shoulder_rx, shoulder_y), int(6*s), GOLD, -1)
        cv2.circle(img, (elbow_rx, elbow_ry), int(5*s), GOLD, -1)
        cv2.circle(img, (hand_rx, hand_ry), int(7*s), WHITE, -1)
        if punch_ext>0.7:
            # impact spark at hand
            cv2.circle(img, (hand_rx, hand_ry), int(12*s*punch_ext), (200,230,255), 2)
            cv2.circle(img, (hand_rx, hand_ry), int(6*s), WHITE, -1)
        # legs - one forward for punch
        fwd = int(punch_ext*18*s)
        left_knee_x = hip_x_left - int(4*s)
        right_knee_x = hip_x_right + fwd//2
        left_foot_x = left_knee_x - int(2*s)
        right_foot_x = right_knee_x + fwd//2
        cv2.line(img, (hip_x_left, hip_y), (left_knee_x, knee_y), WHITE, int(8*s))
        cv2.line(img, (left_knee_x, knee_y), (left_foot_x, foot_y), WHITE, int(7*s))
        cv2.circle(img, (hip_x_left, hip_y), int(6*s), GOLD, -1)
        cv2.circle(img, (left_knee_x, knee_y), int(5*s), GOLD, -1)
        cv2.circle(img, (left_foot_x, foot_y), int(5*s), WHITE, -1)
        cv2.line(img, (hip_x_right, hip_y), (right_knee_x, knee_y), WHITE, int(8*s))
        cv2.line(img, (right_knee_x, knee_y), (right_foot_x, foot_y), WHITE, int(7*s))
        cv2.circle(img, (hip_x_right, hip_y), int(6*s), GOLD, -1)
        cv2.circle(img, (right_knee_x, knee_y), int(5*s), GOLD, -1)
        cv2.circle(img, (right_foot_x, foot_y), int(5*s), WHITE, -1)

    elif pose == 'victory':
        # both arms up
        cv2.line(img, (torso_x, torso_top_y), (torso_x, hip_y), WHITE, int(10*s))
        shoulder_y = torso_top_y + int(12*s)
        shoulder_lx = int(torso_x - torso_w//2)
        shoulder_rx = int(torso_x + torso_w//2)
        # left up
        elbow_lx = int(shoulder_lx - 18*s)
        elbow_ly = int(shoulder_y - 22*s)
        hand_lx = int(elbow_lx - 12*s + math.sin(t*2)*3)
        hand_ly = int(elbow_ly - 28*s)
        cv2.line(img, (shoulder_lx, shoulder_y), (elbow_lx, elbow_ly), WHITE, int(7*s))
        cv2.line(img, (elbow_lx, elbow_ly), (hand_lx, hand_ly), WHITE, int(6*s))
        cv2.circle(img, (shoulder_lx, shoulder_y), int(6*s), GOLD, -1)
        cv2.circle(img, (elbow_lx, elbow_ly), int(5*s), GOLD, -1)
        cv2.circle(img, (hand_lx, hand_ly), int(6*s), WHITE, -1)
        # right up
        elbow_rx = int(shoulder_rx + 18*s)
        elbow_ry = int(shoulder_y - 22*s)
        hand_rx = int(elbow_rx + 12*s + math.sin(t*2+0.5)*3)
        hand_ry = int(elbow_ry - 28*s)
        cv2.line(img, (shoulder_rx, shoulder_y), (elbow_rx, elbow_ry), WHITE, int(7*s))
        cv2.line(img, (elbow_rx, elbow_ry), (hand_rx, hand_ry), WHITE, int(6*s))
        cv2.circle(img, (shoulder_rx, shoulder_y), int(6*s), GOLD, -1)
        cv2.circle(img, (elbow_rx, elbow_ry), int(5*s), GOLD, -1)
        cv2.circle(img, (hand_rx, hand_ry), int(6*s), WHITE, -1)
        # legs
        cv2.line(img, (hip_x_left, hip_y), (hip_x_left, knee_y), WHITE, int(8*s))
        cv2.line(img, (hip_x_left, knee_y), (hip_x_left, foot_y), WHITE, int(7*s))
        cv2.circle(img, (hip_x_left, hip_y), int(6*s), GOLD, -1)
        cv2.circle(img, (hip_x_left, knee_y), int(5*s), GOLD, -1)
        cv2.circle(img, (hip_x_left, foot_y), int(5*s), WHITE, -1)
        cv2.line(img, (hip_x_right, hip_y), (hip_x_right, knee_y), WHITE, int(8*s))
        cv2.line(img, (hip_x_right, knee_y), (hip_x_right, foot_y), WHITE, int(7*s))
        cv2.circle(img, (hip_x_right, hip_y), int(6*s), GOLD, -1)
        cv2.circle(img, (hip_x_right, knee_y), int(5*s), GOLD, -1)
        cv2.circle(img, (hip_x_right, foot_y), int(5*s), WHITE, -1)

    elif pose == 'down':
        # villain knocked down - on ground
        # draw horizontal body
        # torso horizontal
        draw_cx = int(cx)
        draw_cy = int(cy - 14*s)
        # head on ground
        head_cx_d = int(draw_cx + 44*s)
        head_cy_d = int(draw_cy + 4*s)
        # body line horizontal
        torso_left = (draw_cx - int(28*s), draw_cy)
        torso_right = (draw_cx + int(28*s), draw_cy)
        cv2.line(img, torso_left, torso_right, (40,40,60), int(10*s))
        cv2.circle(img, (head_cx_d, head_cy_d), int(18*s), (60,60,80), -1)
        cv2.circle(img, (head_cx_d, head_cy_d), int(18*s), (20,20,30), 2)
        # eyes X (knocked)
        cv2.line(img, (head_cx_d-7, head_cy_d-4), (head_cx_d-2, head_cy_d+2), RED, 2)
        cv2.line(img, (head_cx_d-2, head_cy_d-4), (head_cx_d-7, head_cy_d+2), RED, 2)
        cv2.line(img, (head_cx_d+2, head_cy_d-4), (head_cx_d+7, head_cy_d+2), RED, 2)
        cv2.line(img, (head_cx_d+7, head_cy_d-4), (head_cx_d+2, head_cy_d+2), RED, 2)
        # limbs sprawled
        # arms
        cv2.line(img, torso_left, (torso_left[0]-16, torso_left[1]-16), (50,50,70), int(6*s))
        cv2.line(img, torso_left, (torso_left[0]-10, torso_left[1]+14), (50,50,70), int(6*s))
        cv2.line(img, torso_right, (torso_right[0]+18, torso_right[1]-10), (50,50,70), int(6*s))
        cv2.line(img, torso_right, (torso_right[0]+12, torso_right[1]+16), (50,50,70), int(6*s))
        # legs
        left_hip = (draw_cx - int(22*s), draw_cy)
        right_hip = (draw_cx + int(6*s), draw_cy)
        cv2.line(img, left_hip, (left_hip[0]-20, left_hip[1]+10), (50,50,70), int(7*s))
        cv2.line(img, (left_hip[0]-20, left_hip[1]+10), (left_hip[0]-38, left_hip[1]+8), (50,50,70), int(6*s))
        cv2.line(img, right_hip, (right_hip[0]+24, right_hip[1]+8), (50,50,70), int(7*s))
        cv2.line(img, (right_hip[0]+24, right_hip[1]+8), (right_hip[0]+42, right_hip[1]+12), (50,50,70), int(6*s))
        # shadow bigger
        cv2.ellipse(img, (int(cx), int(cy+10)), (int(56*s), int(12*s)), 0,0,360, (0,0,0), -1)
        return  # skip head draw below

    # head draw (for all except down)
    # head circle white with outline
    cv2.circle(img, (head_cx, head_cy), head_r, WHITE, -1)
    cv2.circle(img, (head_cx, head_cy), head_r, (20,20,20), 2)
    # eyes
    if is_hero:
        eye_y = head_cy + int(2*s)
        eye_lx = head_cx - int(8*s)
        eye_rx = head_cx + int(8*s)
        # visor
        cv2.rectangle(img, (head_cx - int(10*s), eye_y-2), (head_cx + int(10*s), eye_y+2), BLACK, -1)
        cv2.circle(img, (eye_lx, eye_y), int(3*s), BLACK, -1)
        cv2.circle(img, (eye_rx, eye_y), int(3*s), BLACK, -1)
        # highlight
        cv2.circle(img, (head_cx-6, head_cy-6), int(4*s), (255,255,255), -1)
        cv2.circle(img, (head_cx-6, head_cy-6), int(2*s), (200,200,255), -1)
    else:
        eye_y = head_cy + int(3*s)
        eye_lx = head_cx - int(7*s)
        eye_rx = head_cx + int(7*s)
        # red glowing eyes
        cv2.circle(img, (eye_lx, eye_y), int(5*s), RED, -1)
        cv2.circle(img, (eye_rx, eye_y), int(5*s), RED, -1)
        # glow
        cv2.circle(img, (eye_lx, eye_y), int(8*s), (60,60,255), 1)
        cv2.circle(img, (eye_rx, eye_y), int(8*s), (60,60,255), 1)
        cv2.circle(img, (eye_lx, eye_y), int(2*s), WHITE, -1)
        cv2.circle(img, (eye_rx, eye_y), int(2*s), WHITE, -1)

    # chest accent for hero
    if is_hero:
        chest_y = torso_top_y + int(14*s)
        cv2.circle(img, (torso_x, chest_y), int(6*s), GOLD, -1)
        cv2.circle(img, (torso_x, chest_y), int(3*s), (230,240,255), -1)
    else:
        chest_y = torso_top_y + int(14*s)
        cv2.circle(img, (torso_x, chest_y), int(5*s), RED, -1)

    # cape for hero (flutter)
    if is_hero and pose not in ['down']:
        cape_top = (torso_x, torso_top_y + int(6*s))
        flutter = int(math.sin(t*6)*7*s)
        flutter2 = int(math.sin(t*6+1)*5*s)
        pts = np.array([
            [cape_top[0]-int(6*s), cape_top[1]],
            [cape_top[0]+int(6*s), cape_top[1]],
            [cape_top[0]+int(10*s)+flutter, cape_top[1]+int(42*s)],
            [cape_top[0]-int(8*s)+flutter2, cape_top[1]+int(42*s)]
        ], np.int32)
        cv2.fillPoly(img, [pts], (10, 15, 180))
        cv2.polylines(img, [pts], True, (5,5,120), 1)
        # inner highlight
        pts2 = np.array([
            [cape_top[0]-int(3*s), cape_top[1]+4],
            [cape_top[0]+int(3*s), cape_top[1]+4],
            [cape_top[0]+int(6*s)+flutter//2, cape_top[1]+int(32*s)],
            [cape_top[0]-int(4*s)+flutter2//2, cape_top[1]+int(32*s)]
        ], np.int32)
        cv2.fillPoly(img, [pts2], (20, 30, 210))

def draw_text_with_bg(img, text, pos, font_scale=1.0, color=WHITE, bg_color=(0,0,0), center=False, bold=False):
    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = 2 if not bold else 2
    (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = pos
    if center:
        x = x - tw//2
    pad_x, pad_y = 14, 8
    x1, y1 = x - pad_x, y - th - pad_y
    x2, y2 = x + tw + pad_x, y + pad_y
    # simple safe: just draw bg if inside
    if x2>0 and x1<W and y2>0 and y1<H:
        x1c = max(0, x1); y1c = max(0, y1)
        x2c = min(W, x2); y2c = min(H, y2)
        # we keep coords for text baseline within image
        cv2.rectangle(img, (x1c,y1c), (x2c,y2c), bg_color, -1)
        cv2.rectangle(img, (x1c,y1c), (x2c,y2c), (80,80,90), 1)
        # only put text if baseline inside
        if 0 <= x < W and 0 <= y < H:
            cv2.putText(img, text, (x, y), font, font_scale, color, thickness, cv2.LINE_AA)

def draw_impact_ring(img, center, radius, thickness=3, color=WHITE, alpha=0.8):
    overlay = img.copy()
    cv2.circle(overlay, center, radius, color, thickness)
    cv2.circle(overlay, center, int(radius*0.6), color, 2)
    img[:] = cv2.addWeighted(img, 1.0, overlay, alpha, 0)

def draw_frame(frame_idx):
    t = frame_idx / FPS
    img = np.zeros((H,W,3), dtype=np.uint8)

    # BG
    draw_gradient_bg(img, t)
    draw_beams(img, t)
    draw_city(img, t)
    draw_grid_floor(img, t)
    draw_particles(img, t)

    # Timeline positions
    # Hero X
    # Villain X,Y
    # We define hero base X:
    # 0-2: hero slides in from -200 to center
    # else hero near center with slight movements
    # Villain similarly

    hero_x, hero_y = W//2 - 80, int(H*0.72)
    hero_scale = 1.05
    hero_pose = 'idle'
    hero_phase = 0

    villain_x, villain_y = W//2 + 120, int(H*0.72)
    villain_scale = 1.12
    villain_pose = 'idle'
    villain_visible = True

    # Text vars
    top_text = None
    center_text = None
    bottom_text = None
    center_sub = None
    top_sub = None
    bottom_sub = None

    # Impact flash
    flash_alpha = 0

    if t < 2.0:
        # intro
        p = t/2.0
        # hero entry from left
        hero_x = int( lerp(-180, W//2 - 80, ease_in_out(p)) )
        hero_y = int(H*0.72 + math.sin(t*6)*3)
        hero_pose = 'idle'
        villain_visible = False
        top_text = "MONARCHVOICE PRESENTS"
        center_text = "THE STICKMAN"
        center_sub = "REBORN IN 3D • 16:9 CINEMATIC"
        bottom_text = f"{int(p*100)}% LOADING"
        # camera shake subtle
        # flash for intro
        if p < 0.08:
            flash_alpha = 0.25
    elif t < 5.0:
        p = (t-2)/3.0
        hero_x = int( lerp(W//2 - 80, W//2 - 10, ease_in_out(p)) )
        hero_y = int(H*0.72 + math.sin(t*4)*2)
        hero_pose = 'idle'
        villain_visible = False
        top_text = "CHAPTER I: THE CHALLENGE"
        center_text = None
        bottom_text = "20 SECONDS • 16:9 • 60FPS"
        bottom_sub = "REALISTIC LIGHTING • PHYSICS • CINEMATIC CAMERA"
        # slight camera drift will be simulated via city offset already
    elif t < 8.0:
        p = (t-5)/3.0
        hero_x = W//2 - 10 + int(math.sin((t-5)*0.8)*8)
        hero_y = int(H*0.72)
        hero_pose = 'idle'
        villain_visible = False
        top_text = "CITY NEVER SLEEPS"
        center_text = "HERO AWAKENS"
        bottom_text = None
        # hero breathing via draw function t
    elif t < 9.5:
        p = (t-8)/1.5
        villain_visible = True
        # villain drop
        villain_x = W//2 + 120
        villain_y = int( lerp(-180, H*0.72, 1 - (1-p)**3) )  # ease out
        hero_x = W//2 - 10
        hero_y = H*0.72
        hero_pose = 'ready'
        villain_pose = 'idle'
        top_text = "VILLAIN ENTERS"
        center_text = "IMPACT INCOMING"
        if p > 0.88:
            # impact ring
            flash_alpha = 0.35
            # draw impact at villain feet
            # ring will be drawn later
            center_text = "BOOM!"
            # trigger spark
        # subtle shake
        if p>0.92:
            # shake entire image later via translation
            pass
    elif t < 12.0:
        p = (t-9.5)/2.5
        hero_x = W//2 - 18
        hero_y = int(H*0.72)
        villain_x = W//2 + 104 + int(p*16)
        villain_y = int(H*0.72)
        hero_pose = 'ready'
        villain_pose = 'ready'
        top_text = None
        center_text = None
        bottom_text = "FACE OFF"
        bottom_sub = "NEVER OUTSHINE THE MASTER — LAW 01"
        # tension - slight camera shake will be added
    elif t < 14.5:
        p = (t-12)/2.5
        # dodge + punch
        # hero dodge left then punch
        # hero x moves left then right
        dodge = math.sin(p*math.pi) * 52  # left dodge
        hero_x = int(W//2 - 18 - dodge)
        hero_y = int(H*0.72 + math.sin(p*math.pi*2)*8)
        # punch phase for hero
        hero_pose = 'punch'
        hero_phase = p  # 0..1
        villain_x = W//2 + 116 + int(p*22)
        villain_y = int(H*0.72)
        villain_pose = 'ready'
        if p < 0.5:
            center_text = "DODGE!"
        else:
            center_text = "COUNTER!"
            center_sub = "SPEED × PRECISION"
        # impact at p~0.7
        if 0.68 < p < 0.78:
            flash_alpha = 0.28
            center_text = "HIT!"
    elif t < 16.0:
        p = (t-14.5)/1.5
        # slow mo hit
        hero_x = W//2 + 22
        hero_y = int(H*0.72)
        hero_pose = 'punch'
        hero_phase = 0.72 + p*0.1  # hold punch
        villain_x = W//2 + 146 + int(p*12)
        villain_y = int(H*0.72 - p*38)  # villain going down slowly?
        # actually villain should start falling after hit
        # we will handle down pose later
        villain_pose = 'hit'
        # but we will draw villain as hit (shake)
        top_text = "SLOW MOTION IMPACT"
        center_text = None
        bottom_text = "60FPS • MOTION BLUR • PARTICLES"
        flash_alpha = 0.12 * (1-p)
        # slow-mo effect: add motion blur via overlay later
    elif t < 19.0:
        p = (t-16)/3.0
        hero_x = W//2 - 8
        hero_y = int(H*0.72)
        hero_pose = 'victory'
        villain_x = W//2 + 168
        villain_y = int(H*0.72 + 10)
        villain_pose = 'down'
        villain_visible = True
        top_text = None
        center_text = "VICTORY"
        center_sub = "MONARCH RISES"
        bottom_text = "LAW 01 COMPLETE"
        bottom_sub = "NEVER OUTSHINE THE MASTER"
        # gold pulse
        if int(t*4)%2==0:
            flash_alpha = 0.06
    else: # 19-20
        p = (t-19)/1.0
        hero_x = W//2 - 8 + int(math.sin(p*4)*4)
        hero_y = int(H*0.72)
        hero_pose = 'victory'
        villain_x = W//2 + 168
        villain_y = int(H*0.72 + 10)
        villain_pose = 'down'
        top_text = "MONARCHVOICE 3D"
        top_sub = "FULL SERIES COMING SOON"
        center_text = "SUBSCRIBE"
        center_sub = "NEXT LAW DROPS TOMORROW"
        bottom_text = "MADE WITH THREE.JS • CINEMATIC 16:9"
        # flicker
        flash_alpha = random.random()*0.08

    # Draw stickmen
    # Hero
    draw_stickman(img, hero_x, hero_y, hero_scale, hero_pose, t, True, hero_phase)
    # Villain if visible
    if villain_visible:
        if villain_pose == 'hit':
            # shake villain slightly
            shake_x = int(math.sin(t*40)*6)
            shake_y = int(math.sin(t*50)*3)
            draw_stickman(img, villain_x+shake_x, villain_y+shake_y, villain_scale, 'ready', t, False)
        elif villain_pose == 'down':
            draw_stickman(img, villain_x, villain_y, villain_scale, 'down', t, False)
        else:
            draw_stickman(img, villain_x, villain_y, villain_scale, villain_pose, t, False)

    # Impact rings / sparks where needed
    if t < 2 and flash_alpha>0.1:
        # intro flash ring at center
        draw_impact_ring(img, (W//2, int(H*0.68)), int(80 + t*40), 3, GOLD, 0.5)
    if 8.9 < t < 9.8:
        # villain impact
        radius = int(22 + (t-8.9)*80)
        alpha = max(0, 0.8 - (t-8.9)*0.9)
        draw_impact_ring(img, (villain_x, villain_y+8), radius, 4, WHITE, alpha)
        draw_impact_ring(img, (villain_x, villain_y+8), int(radius*0.6), 2, GOLD, alpha*0.7)
        # sparks
        for _ in range(8):
            sx = villain_x + random.randint(-28, 28)
            sy = villain_y - random.randint(20, 50)
            cv2.circle(img, (sx, sy), random.randint(2,5), WHITE, -1)
            cv2.circle(img, (sx, sy), random.randint(1,3), GOLD, -1)
    if 13.5 < t < 14.2:
        # punch impact
        px = hero_x + 48
        py = hero_y - 48
        radius = int(18 + (t-13.5)*70)
        alpha = max(0, 0.9 - (t-13.5)*1.2)
        draw_impact_ring(img, (int(px), int(py)), radius, 3, WHITE, alpha)
        draw_impact_ring(img, (int(px), int(py)), int(radius*0.7), 2, GOLD, alpha)
        for _ in range(10):
            sx = int(px + random.randint(-22, 22) + math.sin(t*30)*6)
            sy = int(py + random.randint(-22, 22))
            cv2.circle(img, (sx, sy), random.randint(2,4), (200,230,255), -1)

    # Text Overlays - draw last so on top
    # Top
    if top_text:
        draw_text_with_bg(img, top_text, (W//2, 42), font_scale=0.62, color=GOLD, bg_color=(12,12,18), center=True)
        if top_sub:
            draw_text_with_bg(img, top_sub, (W//2, 72), font_scale=0.4, color=(200,200,200), bg_color=(12,12,18), center=True)
    # Center
    if center_text:
        # large text with glow
        font_scale = 1.45
        # glow
        overlay = img.copy()
        (tw, th), _ = cv2.getTextSize(center_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, 3)
        cx_t = W//2 - tw//2
        cy_t = H//2 - 10
        cv2.putText(overlay, center_text, (cx_t, cy_t), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (40,40,70), 8, cv2.LINE_AA)
        img[:] = cv2.addWeighted(img, 1.0, overlay, 0.35, 0)
        # main
        cv2.putText(img, center_text, (cx_t, cy_t), cv2.FONT_HERSHEY_SIMPLEX, font_scale, WHITE, 3, cv2.LINE_AA)
        # add gold outline for victory/special
        if center_text in ["VICTORY","SUBSCRIBE","BOOM!","HIT!","DODGE!","COUNTER!"]:
            cv2.putText(img, center_text, (cx_t, cy_t), cv2.FONT_HERSHEY_SIMPLEX, font_scale, GOLD, 1, cv2.LINE_AA)
        if center_sub:
            (tw2, th2), _ = cv2.getTextSize(center_sub, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cx2 = W//2 - tw2//2
            cy2 = H//2 + 28
            draw_text_with_bg(img, center_sub, (W//2, cy2+6), font_scale=0.55, color=(220,220,220), bg_color=(10,10,16), center=True)
    # Bottom
    if bottom_text:
        draw_text_with_bg(img, bottom_text, (W//2, H-38), font_scale=0.52, color=WHITE, bg_color=(10,10,16), center=True)
        if bottom_sub:
            draw_text_with_bg(img, bottom_sub, (W//2, H-14), font_scale=0.38, color=(180,180,190), bg_color=(10,10,16), center=True)

    # HUD - REC + time
    # REC badge
    cv2.rectangle(img, (18, 18), (118, 38), (40,40,255), -1)
    cv2.circle(img, (30, 28), 6, WHITE, -1)
    cv2.putText(img, "REC", (42, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.42, WHITE, 2, cv2.LINE_AA)
    cv2.putText(img, "60FPS", (72, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.38, WHITE, 1, cv2.LINE_AA)
    # time badge
    time_str = f"{int(t)//60:02d}:{int(t)%60:02d} / 00:20  16:9"
    (tw, th), _ = cv2.getTextSize(time_str, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
    cv2.rectangle(img, (W - tw - 28, 18), (W - 12, 38), (0,0,0), -1)
    cv2.rectangle(img, (W - tw - 28, 18), (W - 12, 38), (80,80,80), 1)
    cv2.putText(img, time_str, (W - tw - 20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.42, WHITE, 1, cv2.LINE_AA)
    # progress bar at bottom above text
    bar_y = H - 58
    bar_w = W - 40
    bar_h = 6
    cv2.rectangle(img, (20, bar_y), (20+bar_w, bar_y+bar_h), (40,40,50), -1)
    prog = int(bar_w * (t/DURATION))
    if prog>0:
        cv2.rectangle(img, (20, bar_y), (20+prog, bar_y+bar_h), GOLD, -1)
        # glow
        overlay = img.copy()
        cv2.rectangle(overlay, (20, bar_y-2), (20+prog, bar_y+bar_h+2), GOLD, -1)
        img[:] = cv2.addWeighted(img, 1.0, overlay, 0.18, 0)
    # corner brackets
    for (x1,y1,x2,y2) in [(14,14,40,40),(W-40,14,W-14,40),(14,H-72,40,H-44),(W-40,H-72,W-14,H-44)]:
        cv2.rectangle(img, (x1,y1),(x2,y2), GOLD, 1)
        # inner thicker corner
        cv2.line(img, (x1,y1),(x1+14,y1), GOLD, 2)
        cv2.line(img, (x1,y1),(x1,y1+14), GOLD, 2)

    # Flash / impact white overlay
    if flash_alpha > 0.01:
        flash = np.full((H,W,3), 255, dtype=np.uint8)
        img[:] = cv2.addWeighted(img, 1-flash_alpha, flash, flash_alpha, 0)

    # subtle camera shake for impacts
    if (8.9 < t < 9.3) or (13.6 < t < 14.0):
        shake_x = random.randint(-4,4)
        shake_y = random.randint(-3,3)
        M = np.float32([[1,0,shake_x],[0,1,shake_y]])
        img = cv2.warpAffine(img, M, (W,H), borderMode=cv2.BORDER_REFLECT)

    return img

def main():
    print(f"Generating {DURATION}s video at {W}x{H} {FPS}fps -> {OUTPUT}")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    # Try to use ffmpeg via imageio as fallback if cv2 fails, but cv2 mp4v should work
    out = cv2.VideoWriter(str(OUTPUT), fourcc, FPS, (W,H))
    if not out.isOpened():
        print("CV2 VideoWriter failed, trying alternative with imageio-ffmpeg")
        # fallback to imageio
        import imageio
        writer = imageio.get_writer(str(OUTPUT), fps=FPS, macro_block_size=1)
        for i in range(TOTAL_FRAMES):
            if i % 60 == 0:
                print(f"Frame {i}/{TOTAL_FRAMES} ({i/TOTAL_FRAMES*100:.1f}%)")
            frame = draw_frame(i)
            # imageio expects RGB
            writer.append_data(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        writer.close()
        print(f"Done via imageio: {OUTPUT} size {OUTPUT.stat().st_size/1024/1024:.2f} MB")
        return

    for i in range(TOTAL_FRAMES):
        if i % 60 == 0:
            print(f"Frame {i}/{TOTAL_FRAMES} ({i/TOTAL_FRAMES*100:.1f}%) t={i/FPS:.1f}s")
        frame = draw_frame(i)
        out.write(frame)
    out.release()
    print(f"Done: {OUTPUT} size {OUTPUT.stat().st_size/1024/1024:.2f} MB")
    # Verify with ffprobe via imageio_ffmpeg if needed
    try:
        import subprocess, imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        # re-encode to H.264 for better compatibility using ffmpeg
        tmp = str(OUTPUT).replace(".mp4", "_h264.mp4")
        cmd = [ffmpeg, "-y", "-i", str(OUTPUT), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", tmp]
        print("Re-encoding to H.264 for compatibility...")
        subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import os
        if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            os.replace(tmp, str(OUTPUT))
            print(f"Re-encoded OK: {OUTPUT.stat().st_size/1024/1024:.2f} MB")
    except Exception as e:
        print(f"Re-encode skipped: {e}")

if __name__ == "__main__":
    main()
