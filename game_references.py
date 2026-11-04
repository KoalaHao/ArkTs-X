"""Independent, untimed Python oracles at simulation ticks 8 and 128.

Uses flat actor records instead of virtual calls, per-particle records instead
of SoA, unconditional scene recomputation instead of dirty caching, and sweep
and prune instead of the benchmark's grid. Allocation/pooling share one logical
event oracle because their ownership and results must match.
"""
import json

TICKS = 128
DT = 0.016666666666666666

def capture(values, frame, value):
    if frame in (7, 127):
        values.append(value)

def actors():
    states = [[i % 251 - 125.0 + .1234, (i * 17) % 251 - 125.0 + .4321,
               (i % 19 - 9) * .25, (i % 13 - 6) * .25] for i in range(10000)]
    checks = []
    for frame in range(TICKS):
        total = 0.0
        for i, a in enumerate(states):
            x, y, vx, vy = a
            if i % 3 == 1:
                vx = vx * .999 + ((frame + i % 17) % 17 - 8) * .0001
                vy = vy * .998 + .001
            elif i % 3 == 2:
                vx += (.002 if x < 0 else -.002)
                vy += (.002 if y < 0 else -.002)
            x += vx * DT
            y += vy * DT
            if x >= 128: x -= 256
            if x < -128: x += 256
            if y >= 128: y -= 256
            if y < -128: y += 256
            a[:] = x, y, vx, vy
            total += x * .125 + y * .0625 + vx * .5 + vy
        capture(checks, frame, total)
    return checks

def particles():
    def spawn(i, frame):
        return [(i * 17) % 1024 * .0625 - 32,
                (i * 31) % 512 * .0625,
                (i * 13) % 1024 * .0625 - 32,
                (i % 17 - 8) * .125, 1 + i % 11 * .25,
                (i % 13 - 6) * .125, .05371234567 + (i + frame) % 120 * .0101]
    states = [spawn(i, 0) for i in range(50000)]
    checks = []
    for frame in range(TICKS):
        total = 0.0
        for i, p in enumerate(states):
            p[6] -= DT
            if p[6] <= 0:
                p = spawn(i, frame)
                states[i] = p
            else:
                p[3] += .0001
                p[4] -= .16333333333333333
                p[0] += p[3] * DT
                p[1] += p[4] * DT
                p[2] += p[5] * DT
            total += p[0] * .125 + p[1] * .0625 + p[2] * .03125 + p[6]
        capture(checks, frame, total)
    return checks

def scene():
    local = []
    for i in range(8191):
        rotation = (i % 7 - 3) * .001
        local.append([1 + i % 3 * .0001, -rotation, .001, (i % 17 - 8) * .25,
                      rotation, .99995, -.002, (i % 13 - 6) * .25,
                      -.001, .002, 1.0, (i % 11 - 5) * .25])
    checks = []
    for frame in range(TICKS):
        world = []
        total = 0.0
        for i, matrix in enumerate(local):
            if (i + frame) % 16 == 0:
                matrix[3] += .001
                if matrix[3] > 8: matrix[3] -= 16
            if i == 0:
                result = matrix.copy()
            else:
                parent = world[(i - 1) // 2]
                result = [parent[row * 4] * matrix[col] +
                          parent[row * 4 + 1] * matrix[4 + col] +
                          parent[row * 4 + 2] * matrix[8 + col] +
                          (parent[row * 4 + 3] if col == 3 else 0.0)
                          for row in range(3) for col in range(4)]
            world.append(result)
            x, y, z = result[3], result[7], result[11]
            if -21 <= x <= 21 and -21 <= y <= 21 and -11 <= z <= 41:
                total += 1 + i * .0001 + x * .01 + y * .02 + z * .03
        capture(checks, frame, total)
    return checks

def collisions():
    points = [[(i * 37) % 4096 * .03125 - 64,
               (i * 101) % 4096 * .03125 - 64] for i in range(2048)]
    checks = []
    for frame in range(TICKS):
        for i, p in enumerate(points):
            p[0] += (i % 7 - 3) * .002
            p[1] += (i % 11 - 5) * .002
            for axis in (0, 1):
                if p[axis] >= 64: p[axis] -= 128
                if p[axis] < -64: p[axis] += 128
        order = sorted(range(len(points)), key=lambda i: points[i][0])
        total = 0
        for left, first in enumerate(order):
            x, y = points[first]
            for right in range(left + 1, len(order)):
                second = order[right]
                ax = points[second][0] - x
                if ax >= 1.5: break
                ay = points[second][1] - y
                if ax * ax + ay * ay < 2.25:
                    i, j = sorted((first, second))
                    total += (i + 1) * 3 + (j + 1) * 5
        if frame in (0, 127):
            brute = sum((i + 1) * 3 + (j + 1) * 5
                        for i in range(2048) for j in range(i + 1, 2048)
                        if (points[i][0] - points[j][0]) ** 2 +
                           (points[i][1] - points[j][1]) ** 2 < 2.25)
            assert brute == total
        capture(checks, frame, total)
    return checks

def events():
    health = [50.0] * 4096
    history = [[] for _ in range(8)]
    checks = []
    for frame in range(TICKS):
        values = [((j * 17 + frame % 1024) % 4096,
                   j % 3, (j % 13 + frame % 7) * .125) for j in range(2000)]
        history[frame % 8] = values
        for entity, kind, amount in values:
            h = health[entity] + (-amount if kind == 0 else amount * (.5 if kind == 1 else .125))
            if h < 0: h = 100.0
            if h > 100: h = 0.0
            health[entity] = h
        total = sum(health)
        if frame >= 7:
            for entity, kind, amount in history[(frame + 1) % 8][:64]:
                total += amount * (entity + 1)
        capture(checks, frame, total)
    return checks

def references():
    event_checks = events()
    return dict(behaviours_10k=actors(), particles_50k=particles(),
                scene_8191=scene(), collisions_2048=collisions(),
                events_alloc_2k=event_checks, events_pool_2k=event_checks)

if __name__ == '__main__':
    print(json.dumps(references(), indent=2))
