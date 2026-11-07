"""Quick rule tests: python3 test_kit.py"""
import os, sys, warnings, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kindle_charts as kc, matplotlib.pyplot as plt
kc.OUT = tempfile.mkdtemp() + "/"
def raises(f):
    try: f(); return False
    except ValueError: return True
assert raises(lambda: kc.hbar({str(i): i for i in range(9)}, "t", "s", "a.png", source="Source: x"))
assert raises(lambda: kc.hbar({"a": 1}, "t", "s", "a.png"))                                   # source required
assert raises(lambda: kc.line_chart([1, 2], {str(i): [i, i] for i in range(5)}, "t", "s", "b.png", source="x"))
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    r = kc.stacked_label_bars([("A", "", 3.0, True)], "Old call still works", "sub", "old.png", str, 5)  # old signature
    assert any("source" in str(x.message) for x in w)
assert kc.check_png(r["path"]) == []
fig = plt.figure(figsize=(8, 3)); plt.plot([1, 2], [3, 1], color="#3366cc", lw=0.3)                   # landscape, color, hairline
p = kc.finish(fig, "custom.png"); assert kc.check_png(p) == [], kc.check_png(p)
r = kc.hbar([("A very long category label that keeps going and going", 12.5), ("B", 3)], "Long labels truncate to one line", "s",
            "long.png", source="Example", highlight=0)
assert kc.check_png(r["path"]) == []
r = kc.line_chart(list("abcdef"), {"Up": [-5, -2, 0, 3, 4, 8], "Flat": [1, 1, 1, 1, 1, 1]}, "Neg values", "s", "neg.png", source="Example")
assert kc.check_png(r["path"]) == [] and "Up" in kc.text_fallback(r)
r = kc.slope_chart([("X", 1, 2), ("Y", 1.1, 2.05), ("Z", 1.05, 2.02)], "Close values de-collide", "s", "sl.png", source="Example", highlight="X")
assert kc.check_png(r["path"]) == []
print("all tests passed;", kc.OUT)
