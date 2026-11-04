// Static ArkTS (ArkTS-Sta). No ArkUI, browser, Node, or Flutter dependencies.
class Task {
  readonly id: int;
  weight: number;
  state: int;
  constructor(id: int, weight: number, state: int) {
    this.id = id; this.weight = weight; this.state = state;
  }
}

function sieve(seed: int): number {
  const limit: int = 200000 + seed;
  const composite = new Uint8Array(limit);
  for (let p: int = 2; p * p < limit; p++) {
    if (composite[p] == 0) {
      for (let n: int = p * p; n < limit; n += p) composite[n] = 1;
    }
  }
  let count: int = 0;
  for (let n: int = 2; n < limit; n++) if (composite[n] == 0) count++;
  return count;
}

function vectors(seed: int): number {
  const size: int = 32768;
  const x = new Float64Array(size);
  const y = new Float64Array(size);
  for (let i: int = 0; i < size; i++) {
    x[i] = (i % 97) * 0.125 + seed;
    y[i] = (i % 53) * 0.25;
  }
  for (let pass: int = 0; pass < 12; pass++) {
    for (let i: int = 0; i < size; i++) {
      x[i] = x[i] * 0.999 + y[i] * 0.001;
      y[i] = y[i] * 0.998 + x[i] * 0.002;
    }
  }
  let sum: number = 0.0;
  for (let i: int = 0; i < size; i++) sum += x[i] + y[i];
  return sum;
}

function objects(seed: int): number {
  const tasks: Task[] = [];
  for (let i: int = 0; i < 10000; i++) {
    tasks.push(new Task(i, (i % 31) * 0.25 + seed, i % 4));
  }
  for (let pass: int = 0; pass < 4; pass++) {
    for (let i: int = 0; i < tasks.length; i++) {
      const task = tasks[i];
      task.weight = task.weight * 1.001 + task.state;
      task.state = (task.state + 1) % 4;
    }
  }
  let sum: number = 0.0;
  for (let i: int = 0; i < tasks.length; i++) sum += tasks[i].weight + tasks[i].id;
  return sum;
}

let textFixture: string = '';
function prepareText(): void {
  const lines: string[] = [];
  for (let i: int = 0; i < 4096; i++) {
    const tag: string = i % 7 == 0 ? 'ERROR' : 'INFO';
    lines.push(tag + ':review src/agent_' + (i % 97).toString() + '.dart 内容');
  }
  textFixture = lines.join('\n');
}

function text(seed: int): number {
  const lines = textFixture.split('\n');
  let sum: number = seed;
  for (let i: int = 0; i < lines.length; i++) {
    const line = lines[i];
    const colon = line.indexOf(':');
    const tag = line.substring(0, colon);
    const body = line.substring(colon + 1);
    if (tag == 'ERROR') sum += body.length * 3;
    else sum += body.length;
  }
  return sum;
}

function work(kind: int, seed: int): number {
  if (kind == 0) return sieve(seed);
  if (kind == 1) return vectors(seed);
  if (kind == 2) return objects(seed);
  return text(seed);
}

function measure(kind: int, name: string): void {
  const check = work(kind, 1);
  let sink: number = 0.0;
  let batch: int = 1;
  const warmStart = Date.now();
  while (Date.now() - warmStart < 1000) {
    const start = Date.now();
    for (let i: int = 0; i < batch; i++) sink += work(kind, 1 + i % 7);
    if (Date.now() - start < 100 && batch < 8192) batch *= 2;
  }
  const samples: number[] = [];
  for (let sample: int = 0; sample < 5; sample++) {
    const start = Date.now();
    for (let i: int = 0; i < batch; i++) sink += work(kind, 1 + i % 7);
    const elapsed: number = Long.toDouble(Date.now() - start);
    samples.push(elapsed / batch);
  }
  console.log('BENCH {"name":"' + name + '","batch":' + batch.toString() +
    ',"check":' + check.toString() + ',"sink":' + sink.toString() +
    ',"ms_per_op":[' + samples.join(',') + ']}');
}

function main(): void {
  prepareText();
  measure(0, 'sieve');
  measure(1, 'vectors');
  measure(2, 'objects');
  measure(3, 'text');
}
