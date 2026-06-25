export default {
  template: `
    <div class="w-full">
      <q-linear-progress :value="level" color="accent" track-color="grey-3" class="q-mt-xs"/>
      <div class="text-caption text-grey">{{ statusText }}</div>
    </div>
  `,
  data() {
    return {
      level: 0,
      armed: false,
      threshold: 0.12,
      statusText: "",
      lastClapMs: 0,
      stream: null,
      audioContext: null,
      analyser: null,
      rafId: null,
    };
  },
  beforeUnmount() {
    this.disarm();
  },
  methods: {
    async arm(threshold) {
      this.disarm();
      this.threshold = threshold || 0.12;
      this.armed = true;
      this.statusText = "Mikrofon aktiv — klatschen oder rufen";
      try {
        this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (error) {
        this.armed = false;
        this.statusText = "Mikrofon nicht verfuegbar";
        this.$emit("error", { message: error.message || String(error) });
        return;
      }
      this.audioContext = new AudioContext();
      const source = this.audioContext.createMediaStreamSource(this.stream);
      this.analyser = this.audioContext.createAnalyser();
      this.analyser.fftSize = 2048;
      source.connect(this.analyser);
      this._tick();
    },
    disarm() {
      this.armed = false;
      if (this.rafId !== null) {
        cancelAnimationFrame(this.rafId);
        this.rafId = null;
      }
      if (this.stream) {
        this.stream.getTracks().forEach((track) => track.stop());
        this.stream = null;
      }
      if (this.audioContext) {
        this.audioContext.close();
        this.audioContext = null;
      }
      this.analyser = null;
      this.level = 0;
      if (!this.statusText.startsWith("Start")) {
        this.statusText = "";
      }
    },
    _tick() {
      if (!this.armed || !this.analyser) {
        return;
      }
      const data = new Uint8Array(this.analyser.fftSize);
      this.analyser.getByteTimeDomainData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i += 1) {
        const sample = (data[i] - 128) / 128;
        sum += sample * sample;
      }
      const rms = Math.sqrt(sum / data.length);
      this.level = Math.min(1, rms * 6);
      const now = Date.now();
      if (rms >= this.threshold && now - this.lastClapMs > 1200) {
        this.lastClapMs = now;
        this.statusText = "Start erkannt!";
        this.$emit("clap", { rms });
        this.disarm();
        return;
      }
      this.rafId = requestAnimationFrame(() => this._tick());
    },
  },
};
