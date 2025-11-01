import os, yaml, importlib.util, sys

class Agent:
    def __init__(self, name: str, root: str = None):
        self.name = name
        self.root = root or os.getcwd()
        self._run_fn = None
    def runner(self, fn):
        self._run_fn = fn
        return fn
    def run(self, inputs: dict, ctx: dict):
        if not self._run_fn:
            raise RuntimeError("No run function registered")
        return self._run_fn(inputs, ctx)

def load_manifest(path: str):
    with open(path, "r") as f: return yaml.safe_load(f)


def load_module(path: str):
    agent_dir = os.path.dirname(path)
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)  # <-- so `model_utils` is importable
    spec = importlib.util.spec_from_file_location("agent_module", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

#def load_module(path: str):
#    spec = importlib.util.spec_from_file_location("agent_module", path)
#    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
#    return mod

def load_agent(agent_dir: str) -> Agent:
    _ = load_manifest(os.path.join(agent_dir, "agent.yaml"))
    mod = load_module(os.path.join(agent_dir, "agent.py"))
    if not hasattr(mod, "agent"): raise RuntimeError("Agent module missing `agent`")
    return mod.agent
