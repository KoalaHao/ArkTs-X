class OsrLiveBox {
  label: string;
  constructor(seed: int) { this.label = 'live 内容 ' + seed.toString(); }
}

function spin(seed: int): number {
  const box = new OsrLiveBox(seed);
  let value: number = seed;
  for (let i: int = 0; i < 10000000; i++) value = value * 0.999999 + i * 0.000001;
  const id = GC.startGC(GC.Cause.FULL, GC.IN_PLACE_MODE);
  GC.waitForFinishGC(id);
  if (id < 0 || box.label != 'live 内容 1') throw new Error('OSR live reference mismatch');
  return value + box.label.length;
}

function main(): void { console.log('OSR_SMOKE ' + spin(1).toString()); }
