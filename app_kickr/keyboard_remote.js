export default {
  template: '<div style="display:none" aria-hidden="true"></div>',
  data() {
    return {
      active: true,
      debugMode: false,
      lastKeyMs: 0,
    };
  },
  mounted() {
    this._handler = (event) => this._onKey(event);
    window.addEventListener("keydown", this._handler);
  },
  beforeUnmount() {
    window.removeEventListener("keydown", this._handler);
  },
  methods: {
    enable() {
      this.active = true;
    },
    disable() {
      this.active = false;
    },
    set_debug_mode(enabled) {
      this.debugMode = !!enabled;
    },
    _emitDebug(event) {
      this.$emit("key_debug", {
        key: event.key,
        code: event.code,
        keyCode: event.keyCode,
        location: event.location,
      });
    },
    _matchAction(event) {
      const key = event.key;
      const code = event.code;
      const powerUpKeys = new Set(["PageUp", "ArrowUp"]);
      const powerDownKeys = new Set(["PageDown", "ArrowDown"]);
      const transportKeys = new Set([
        "Enter",
        " ",
        "F5",
        "Escape",
        "Play",
        "Pause",
        "MediaPlayPause",
        "MediaPlay",
        "MediaPause",
        "ArrowRight",
      ]);
      const stopKeys = new Set([
        "End",
        "F6",
        "MediaStop",
        ".",
        "Period",
      ]);

      if (powerUpKeys.has(key) || code === "PageUp" || code === "ArrowUp") {
        return "power_up";
      }
      if (powerDownKeys.has(key) || code === "PageDown" || code === "ArrowDown") {
        return "power_down";
      }
      if (
        transportKeys.has(key)
        || code === "MediaPlayPause"
        || code === "MediaPlay"
        || code === "MediaPause"
        || code === "Escape"
      ) {
        return "transport";
      }
      if (stopKeys.has(key) || code === "MediaStop" || code === "Period") {
        return "stop";
      }
      return null;
    },
    _onKey(event) {
      if (!this.active) {
        return;
      }
      if (this.debugMode) {
        event.preventDefault();
        this._emitDebug(event);
        return;
      }
      const tag = document.activeElement?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
        return;
      }
      if (event.repeat) {
        return;
      }
      const now = Date.now();
      if (now - this.lastKeyMs < 180) {
        return;
      }
      const action = this._matchAction(event);
      if (!action) {
        this._emitDebug(event);
        return;
      }
      event.preventDefault();
      this.lastKeyMs = now;
      this.$emit(action, { key: event.key, code: event.code });
    },
  },
};
