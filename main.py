self.train = Train(self.manager)
        self._update_hud()
        self._refresh_preview()

    def set_segment_type(self, idx):
        self.segment_idx = idx
        self._refresh_preview()
        self._update_hud()

    def set_color(self, key):
        self.color_key = key
        self._refresh_preview()
        self._update_hud()

    def _on_toggle(self, running):
        self.running = running
        if running: 
            self.train.start()
        else: 
            self.train.stop()

    def place(self):
        c = TRACK_COLORS[self.color_key]
        factory = SEGMENT_FACTORIES[self.segment_idx][1]
        self.manager.add_segment(factory(c))
        self._refresh_preview()
        self._update_hud()

    def undo(self):
        self.manager.remove_last()
        self._refresh_preview()
        self._update_hud()

    def clear_track(self):
        self.train.stop()
        self.running = False
        self.controls.toggle() # Setzt den Button UI zurück
        self.manager.clear()
        self._refresh_preview()
        self._update_hud()

    def next_type(self):
        self.segment_idx = (self.segment_idx + 1) % len(SEGMENT_FACTORIES)
        self.palette.select(self.segment_idx)
        self._refresh_preview()
        self._update_hud()

    def next_color(self):
        idx = COLOR_KEYS.index(self.color_key)
        self.color_key = COLOR_KEYS[(idx + 1) % len(COLOR_KEYS)]
        self.color_ui.select(self.color_key)
        self._refresh_preview()
        self._update_hud()

    def _refresh_preview(self):
        if self._preview: 
            destroy(self._preview)
        c = TRACK_COLORS[self.color_key]
        factory = SEGMENT_FACTORIES[self.segment_idx][1]
        # Erzeugt eine halbtransparente Vorschau
        preview_seg = factory(color.rgba(c.r, c.g, c.b, 0.35))
        self._preview = preview_seg.spawn()
        # Nutzt die Transformation aus deiner Trackmanager-Klasse
        if hasattr(self.manager, 'apply_exit_transformation'):
            self.manager.apply_exit_transformation(self._preview)

    def _update_hud(self):
        self._hud.text = f"Teile: {len(self.manager.segments)}\n[RÜCKTASTE] Undo\n[C] Clear\n[ENTER] Start"

# --- 8. GLOBAL EVENTS & CALLBACKS ---
state = None

def update():
    if state and state.running:
        # Bewegt den Zug basierend auf dem Speed-Slider in den Controls
        state.train.update(state.controls.speed)

def input(key):
    if not state: 
        return
    if key == "space": 
        state.place()
    elif key == "backspace": 
        state.undo()
    elif key == "tab": 
        state.next_type()
    elif key == "q": 
        state.next_color()
    elif key == "c": 
        state.clear_track()
    elif key == "enter": 
        state.controls.toggle()

# --- 9. STARTPUNKT ---
if __name__ == "__main__":
    setup_lighting()
    create_ground()
    Sky()
    state = GameState()
    EditorCamera() # Erlaubt freies Bewegen der Kamera
    app.run()
