"""ctypes bindings for the engine's built-in search (reverse-engineered signatures)."""
import ctypes, json, random
from collections import Counter
from kaggle_environments.envs.cabt.cg import sim
from kaggle_environments.envs.cabt.cg.sim import SerialData

lib = sim.lib
lib.AgentStart.restype = ctypes.c_void_p
lib.AgentStart.argtypes = []
IntP = ctypes.POINTER(ctypes.c_int)
lib.SearchBegin.restype = ctypes.c_char_p
lib.SearchBegin.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, IntP, IntP, IntP, IntP, IntP, IntP, ctypes.c_int]
lib.SearchStep.restype = ctypes.c_char_p
lib.SearchStep.argtypes = [ctypes.c_void_p, ctypes.c_int, IntP, ctypes.c_int]
lib.SearchRelease.argtypes = [ctypes.c_void_p, ctypes.c_int]
lib.SearchEnd.argtypes = [ctypes.c_void_p]

_CTX = None


def ctx():
    global _CTX
    if _CTX is None:
        _CTX = lib.AgentStart()
    return _CTX


def _arr(xs):
    xs = list(xs) or [0]
    return (ctypes.c_int * len(xs))(*xs)


def _decode(sd):
    out = json.loads(sd.decode()) if sd else None
    return out


def begin(search_input, your_deck, your_prize, opp_deck, opp_prize, opp_hand, opp_active=(), manual_coin=False):
    b = search_input.encode("ascii")
    sd = lib.SearchBegin(ctx(), b, len(b), _arr(your_deck), _arr(your_prize), _arr(opp_deck), _arr(opp_prize),
                         _arr(opp_hand), _arr(opp_active), int(manual_coin))
    return _decode(sd)


def step(search_id, select):
    sd = lib.SearchStep(ctx(), int(search_id), _arr(select), len(select))
    return _decode(sd)


def release(search_id):
    lib.SearchRelease(ctx(), int(search_id))


def end():
    lib.SearchEnd(ctx())
