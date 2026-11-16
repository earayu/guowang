class Context:
    def search(self, *a, **k): return []
    def step(self, *a, **k): 
        import contextlib
        return contextlib.nullcontext()
