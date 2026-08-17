# conftest.py
#
# Minimal import shim, NOT the domain/adapters restructure that's still an
# open decision. The test files import `domain.X`, but no `domain` package
# exists -- the real modules live scattered across Latent/, Domain/, Sim/,
# Model/, SDK/, API/.
#
# Expanded 2026-07-01: originally aliased only LatentPayload/CallerState (the
# two the latent tests need). Now aliases everything else referenced across
# the test suite so every file at least COLLECTS. This does NOT mean every
# file PASSES -- for several, aliasing correctly reveals a real constructor/
# method contract mismatch between the test and the implementation (the same
# "two designs never reconciled" pattern as the RL engines), instead of
# hiding it behind an opaque ModuleNotFoundError. That's the point: an honest
# failure is more useful than a mysterious import error. See CHANGES.md for
# which files pass outright vs. which now fail on the real, more informative
# error.

import sys
import types
import pathlib

_HERE = pathlib.Path(__file__).parent.parent
for _sub in ("Latent", "Domain", "Sim", "Model", "SDK", "API", "Engines", "Registry", "Telemetry", "Replay"):
    sys.path.insert(0, str(_HERE / _sub))

import LatentPayload as _latent_payload   # noqa: E402
import CallerState as _caller_state       # noqa: E402
import QueueState as _queue_state         # noqa: E402
import Simulator as _simulator            # noqa: E402
import Build_Graph as _build_graph        # noqa: E402
import Telemetry as _telemetry            # noqa: E402
import Replay as _replay                  # noqa: E402
import cluster_runner as _cluster_runner  # noqa: E402
import rl_ppo as _rl_ppo                  # noqa: E402
import rl_marl as _rl_marl                # noqa: E402
import server as _api_server              # noqa: E402
# staffing_rl removed 2026-07-02: StaffingRLEngine required AHT, shrinkage,
# and answered-vs-offered data -- none of which Iceberg can ever see, by its
# own scope boundary (objective ends at the ACD door). Not deprioritized,
# epistemically impossible from where Iceberg sits. Engines/staffing_rl.py
# and Tests/test_staffing_rl.py were deleted, not stubbed.

_api_pkg = types.ModuleType("api")
sys.modules["api"] = _api_pkg
sys.modules["api.server"] = _api_server
_api_pkg.server = _api_server

_domain_pkg = types.ModuleType("domain")
sys.modules["domain"] = _domain_pkg

_aliases = {
    "LatentPayload": _latent_payload,
    "CallerState": _caller_state,
    "QueueState": _queue_state,
    "simulator": _simulator,       # test files import lowercase `domain.simulator`
    "build_graph": _build_graph,   # and lowercase `domain.build_graph`
    "telemetry": _telemetry,
    "replay": _replay,
    "cluster_runner": _cluster_runner,
    "rl_ppo": _rl_ppo,
    "rl_marl": _rl_marl,
}
for _name, _mod in _aliases.items():
    sys.modules[f"domain.{_name}"] = _mod
    setattr(_domain_pkg, _name, _mod)

# bayes_gpu deliberately NOT aliased -- separate, narrower issue (parameter
# name mismatch: `likelihood` vs `likelihoods`), not the architecture fork.
