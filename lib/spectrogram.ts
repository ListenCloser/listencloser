/**
 * Deterministic, client-side spectrogram primitives.
 *
 * These are presentation measurements of an AudioBuffer, not music-analysis
 * claims. Keeping the coordinate math separate makes interaction behavior
 * independently testable and lets the canvas component stay focused on I/O.
 */

export const SPECTROGRAM_FFT_SIZE = 2048;
export const SPECTROGRAM_BINS = 128;
export const SPECTROGRAM_MIN_FREQUENCY = 40;

export type SpectrogramData = {
  columns: number;
  bins: number;
  duration: number;
  minFrequency: number;
  maxFrequency: number;
  values: Uint8Array;
};

export type SpectrogramOptions = {
  fftSize?: number;
  bins?: number;
  maxColumns?: number;
  minFrequency?: number;
  onProgress?: (completed: number, total: number) => void;
  yieldToBrowser?: () => Promise<void>;
};

export function clamp(value: number, lower: number, upper: number): number {
  return Math.min(upper, Math.max(lower, value));
}

export function timeToX(time: number, duration: number, width: number): number {
  return duration > 0 ? (clamp(time, 0, duration) / duration) * width : 0;
}

export function xToTime(x: number, width: number, duration: number): number {
  return width > 0 ? clamp(x / width, 0, 1) * duration : 0;
}

/** Map a frequency to a canvas y coordinate using a logarithmic frequency axis. */
export function frequencyToY(
  frequency: number,
  minFrequency: number,
  maxFrequency: number,
  height: number,
): number {
  if (height <= 0 || maxFrequency <= minFrequency) return height;
  const ratio = Math.log(clamp(frequency, minFrequency, maxFrequency) / minFrequency)
    / Math.log(maxFrequency / minFrequency);
  return height * (1 - ratio);
}

/** Return FFT-bin indices that correspond to logarithmically spaced display rows. */
export function logarithmicBinMap(
  bins: number,
  sampleRate: number,
  fftSize: number,
  minFrequency: number,
): Uint16Array {
  const result = new Uint16Array(bins);
  const maxBin = fftSize / 2;
  const maxFrequency = sampleRate / 2;
  for (let row = 0; row < bins; row += 1) {
    const ratio = bins === 1 ? 0 : row / (bins - 1);
    const frequency = minFrequency * Math.pow(maxFrequency / minFrequency, ratio);
    result[row] = clamp(Math.round((frequency / sampleRate) * fftSize), 1, maxBin - 1);
  }
  return result;
}

function hann(index: number, size: number): number {
  return 0.5 - 0.5 * Math.cos((2 * Math.PI * index) / (size - 1));
}

/** In-place radix-2 Cooley–Tukey FFT for the visualization's real-valued window. */
function fft(real: Float64Array, imaginary: Float64Array): void {
  const size = real.length;
  for (let i = 1, bit = 0; i < size; i += 1) {
    let mask = size >> 1;
    for (; bit & mask; mask >>= 1) bit ^= mask;
    bit ^= mask;
    if (i < bit) {
      [real[i], real[bit]] = [real[bit], real[i]];
      [imaginary[i], imaginary[bit]] = [imaginary[bit], imaginary[i]];
    }
  }
  for (let span = 2; span <= size; span <<= 1) {
    const angle = (-2 * Math.PI) / span;
    const stepReal = Math.cos(angle);
    const stepImaginary = Math.sin(angle);
    for (let start = 0; start < size; start += span) {
      let weightReal = 1;
      let weightImaginary = 0;
      const half = span >> 1;
      for (let offset = 0; offset < half; offset += 1) {
        const even = start + offset;
        const odd = even + half;
        const transformedReal = weightReal * real[odd] - weightImaginary * imaginary[odd];
        const transformedImaginary = weightReal * imaginary[odd] + weightImaginary * real[odd];
        real[odd] = real[even] - transformedReal;
        imaginary[odd] = imaginary[even] - transformedImaginary;
        real[even] += transformedReal;
        imaginary[even] += transformedImaginary;
        const nextReal = weightReal * stepReal - weightImaginary * stepImaginary;
        weightImaginary = weightReal * stepImaginary + weightImaginary * stepReal;
        weightReal = nextReal;
      }
    }
  }
}

/**
 * Compute a bounded full-recording spectrogram. Work is yielded in small
 * chunks so ordinary recordings do not monopolize the UI thread.
 */
export async function computeSpectrogram(
  samples: Float32Array,
  sampleRate: number,
  options: SpectrogramOptions = {},
): Promise<SpectrogramData> {
  const fftSize = options.fftSize ?? SPECTROGRAM_FFT_SIZE;
  const bins = options.bins ?? SPECTROGRAM_BINS;
  const maxColumns = options.maxColumns ?? 720;
  const minFrequency = options.minFrequency ?? SPECTROGRAM_MIN_FREQUENCY;
  if (fftSize < 2 || (fftSize & (fftSize - 1)) !== 0) throw new Error("fftSize must be a power of two");
  const duration = samples.length / sampleRate;
  const columns = Math.max(1, Math.min(maxColumns, Math.ceil(samples.length / Math.max(1, fftSize / 2))));
  const hop = Math.max(1, Math.floor(Math.max(0, samples.length - fftSize) / Math.max(1, columns - 1)));
  const values = new Uint8Array(columns * bins);
  const binMap = logarithmicBinMap(bins, sampleRate, fftSize, minFrequency);
  const real = new Float64Array(fftSize);
  const imaginary = new Float64Array(fftSize);
  const yieldToBrowser = options.yieldToBrowser ?? (() => new Promise<void>((resolve) => window.setTimeout(resolve, 0)));

  for (let column = 0; column < columns; column += 1) {
    real.fill(0);
    imaginary.fill(0);
    const start = Math.min(column * hop, Math.max(0, samples.length - fftSize));
    for (let index = 0; index < fftSize; index += 1) real[index] = (samples[start + index] ?? 0) * hann(index, fftSize);
    fft(real, imaginary);
    for (let row = 0; row < bins; row += 1) {
      const bin = binMap[row];
      const magnitude = Math.sqrt(real[bin] ** 2 + imaginary[bin] ** 2) / fftSize;
      // -90dB..0dB -> 0..255. The gentle gamma keeps quiet harmonics legible.
      const normalized = clamp((20 * Math.log10(magnitude + 1e-9) + 90) / 90, 0, 1);
      values[column * bins + row] = Math.round(Math.pow(normalized, 0.72) * 255);
    }
    options.onProgress?.(column + 1, columns);
    if ((column + 1) % 8 === 0 && column + 1 < columns) await yieldToBrowser();
  }
  return { columns, bins, duration, minFrequency, maxFrequency: sampleRate / 2, values };
}
