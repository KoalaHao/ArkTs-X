// Runtime correctness probe; its elapsed time is not a benchmark result.
class PortProbeBox {
  value: int;
  label: string;
  constructor(value: int) {
    this.value = value;
    this.label = 'crux 内容 ' + value.toString();
  }
}

function recurse(n: int): int {
  if (n == 0) return 1;
  return n + recurse(n - 1);
}

function numeric(seed: int): number {
  let total: number = seed;
  for (let i: int = 0; i < 64; i++) total = total * 0.999 + i * 0.125;
  return total;
}

function allocate(seed: int): int {
  const keep = new PortProbeBox(seed);
  const boxes: PortProbeBox[] = [];
  for (let i: int = 0; i < 100; i++) boxes.push(new PortProbeBox(seed + i));
  let total: int = keep.value;
  for (let i: int = 0; i < boxes.length; i++) {
    if (!boxes[i].label.startsWith('crux 内容 ')) throw new Error('Unicode mismatch');
    total += boxes[i].value;
  }
  return total;
}

function throwAtSeven(n: int): int {
  if (n == 7) throw new Error('expected');
  return n;
}

function main(): void {
  const anchor = new PortProbeBox(123);
  let total: number = 0.0;
  let allocations: long = 0;
  let collections: int = 0;
  let reclaimed: long = 0;
  for (let i: int = 0; i < 10000; i++) {
    total += numeric(i % 17);
    allocations += allocate(i % 17);
    if (i % 2500 == 0) {
      const before = GC.getUsedHeapSize();
      const id = GC.startGC(GC.Cause.FULL, GC.IN_PLACE_MODE);
      GC.waitForFinishGC(id);
      if (id < 0 || anchor.value != 123 || anchor.label != 'crux 内容 123') {
        throw new Error('GC/live reference mismatch');
      }
      const after = GC.getUsedHeapSize();
      if (before > after) reclaimed += before - after;
      collections++;
    }
  }
  let caught: int = 0;
  let remaining: int = 0;
  for (let i: int = 0; i < 16; i++) {
    try { remaining += throwAtSeven(i); }
    catch (e) { caught++; }
  }
  if (recurse(100) != 5051 || caught != 1 || remaining != 113) {
    throw new Error('recursion/exception mismatch');
  }
  console.log('PORT_SMOKE ' + total.toString() + ' ' + allocations.toString() +
    ' ' + caught.toString() + ' ' + remaining.toString());
  console.log('PORT_GC ' + collections.toString() + ' ' + anchor.value.toString() +
    ' ' + reclaimed.toString());
}
