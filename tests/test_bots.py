from SOLUSDBOT_main_shim import compute_grid

def test_compute_grid():
    g = compute_grid(100, 200, 11)
    assert len(g) == 11
    assert g[0] == 100
    assert g[-1] == 200
