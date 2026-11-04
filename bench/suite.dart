import 'dart:convert';
import 'dart:typed_data';

class Task {
  final int id;
  double weight;
  int state;
  Task(this.id, this.weight, this.state);
}

double sieve(int seed) {
  final limit = 200000 + seed;
  final composite = Uint8List(limit);
  for (var p = 2; p * p < limit; p++) {
    if (composite[p] == 0) {
      for (var n = p * p; n < limit; n += p) composite[n] = 1;
    }
  }
  var count = 0;
  for (var n = 2; n < limit; n++) {
    if (composite[n] == 0) count++;
  }
  return count.toDouble();
}

double vectors(int seed) {
  const size = 32768;
  final x = Float64List(size);
  final y = Float64List(size);
  for (var i = 0; i < size; i++) {
    x[i] = (i % 97) * 0.125 + seed;
    y[i] = (i % 53) * 0.25;
  }
  for (var pass = 0; pass < 12; pass++) {
    for (var i = 0; i < size; i++) {
      x[i] = x[i] * 0.999 + y[i] * 0.001;
      y[i] = y[i] * 0.998 + x[i] * 0.002;
    }
  }
  var sum = 0.0;
  for (var i = 0; i < size; i++) sum += x[i] + y[i];
  return sum;
}

double objects(int seed) {
  final tasks = <Task>[];
  for (var i = 0; i < 10000; i++) {
    tasks.add(Task(i, (i % 31) * 0.25 + seed, i % 4));
  }
  for (var pass = 0; pass < 4; pass++) {
    for (var i = 0; i < tasks.length; i++) {
      final task = tasks[i];
      task.weight = task.weight * 1.001 + task.state;
      task.state = (task.state + 1) % 4;
    }
  }
  var sum = 0.0;
  for (var i = 0; i < tasks.length; i++) {
    sum += tasks[i].weight + tasks[i].id;
  }
  return sum;
}

var textFixture = '';
void prepareText() {
  final lines = <String>[];
  for (var i = 0; i < 4096; i++) {
    final tag = i % 7 == 0 ? 'ERROR' : 'INFO';
    lines.add('$tag:review src/agent_${i % 97}.dart 内容');
  }
  textFixture = lines.join('\n');
}

double text(int seed) {
  final lines = textFixture.split('\n');
  var sum = seed;
  for (var i = 0; i < lines.length; i++) {
    final line = lines[i];
    final colon = line.indexOf(':');
    final tag = line.substring(0, colon);
    final body = line.substring(colon + 1);
    if (tag == 'ERROR') {
      sum += body.length * 3;
    } else {
      sum += body.length;
    }
  }
  return sum.toDouble();
}

double work(int kind, int seed) {
  if (kind == 0) return sieve(seed);
  if (kind == 1) return vectors(seed);
  if (kind == 2) return objects(seed);
  return text(seed);
}

void measure(int kind, String name) {
  final check = work(kind, 1);
  var sink = 0.0;
  var batch = 1;
  final clock = Stopwatch()..start();
  while (clock.elapsedMilliseconds < 1000) {
    final start = clock.elapsedMilliseconds;
    for (var i = 0; i < batch; i++) sink += work(kind, 1 + i % 7);
    if (clock.elapsedMilliseconds - start < 100 && batch < 8192) batch *= 2;
  }
  final samples = <double>[];
  for (var sample = 0; sample < 5; sample++) {
    final start = clock.elapsedMilliseconds;
    for (var i = 0; i < batch; i++) sink += work(kind, 1 + i % 7);
    final elapsed = clock.elapsedMilliseconds - start;
    samples.add(elapsed / batch);
  }
  print(
    'BENCH ${jsonEncode({'name': name, 'batch': batch, 'check': check, 'sink': sink, 'ms_per_op': samples})}',
  );
}

void main() {
  prepareText();
  measure(0, 'sieve');
  measure(1, 'vectors');
  measure(2, 'objects');
  measure(3, 'text');
}
