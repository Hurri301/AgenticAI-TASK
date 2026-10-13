from mm_link.projection import minimum_circular_interval, project_world_to_pano_pixels


def test_projection_wraparound_and_flip():
    W, H = 1000, 500
    t = (0.0, 0.0, 0.0)
    R = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    pts = [
        (1.0, 1e-6, 0.0),
        (1.0, -1e-6, 0.0),
    ]

    uv, valid = project_world_to_pano_pixels(pts, t, R, (W, H), v_top=0, v_bottom=H, flip_pano_u=False)
    assert all(valid)
    assert uv[0][0] > uv[1][0]

    uv_flip, valid_flip = project_world_to_pano_pixels(pts, t, R, (W, H), v_top=0, v_bottom=H, flip_pano_u=True)
    assert all(valid_flip)
    assert uv_flip[0][0] < uv_flip[1][0]

    u0, u1 = minimum_circular_interval([998.0, 2.0], W)
    assert u0 > u1
