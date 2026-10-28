// Seeded samplers shared by the methods illustrations.
export function gammaSampler(seed) {
  const uniform = () => ((seed = (Math.imul(1664525, seed) + 1013904223) >>> 0) + 0.5) / 4294967296;
  const normal = () => Math.sqrt(-2 * Math.log(uniform())) * Math.cos(2 * Math.PI * uniform());
  const logGamma = (shape) => {
    if (shape < 1) return logGamma(shape + 1) + Math.log(uniform()) / shape;
    const d = shape - 1 / 3,
      c = 1 / Math.sqrt(9 * d);
    for (;;) {
      const x = normal(),
        v = (1 + c * x) ** 3;
      if (v <= 0) continue;
      const u = uniform();
      if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return Math.log(d * v);
    }
  };
  const poisson = (mean) => {
    let count = 0;
    while (mean > 0) {
      const chunk = Math.min(20, mean),
        limit = Math.exp(-chunk);
      let product = 1,
        n = -1;
      do {
        product *= uniform();
        n++;
      } while (product > limit);
      count += n;
      mean -= chunk;
    }
    return count;
  };
  return { uniform, logGamma, gamma: (shape) => Math.exp(logGamma(shape)), poisson };
}
