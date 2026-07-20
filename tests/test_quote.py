from services.quote_service import calculate_quote, get_base_price


def test_base_price_and_source_file_default_off():
    quote = calculate_quote("商业海报")
    assert quote["base_price"] == 69
    assert quote["source_file_fee"] == 0
    assert quote["final_price"] == 69


def test_urgent_12_and_24_hour_tiers():
    assert calculate_quote("小红书封面", hours_until_deadline=12)["urgent_fee"] == 40
    assert calculate_quote("小红书封面", hours_until_deadline=24)["urgent_fee"] == 20
    assert calculate_quote("小红书封面", hours_until_deadline=25)["urgent_fee"] == 0
    assert calculate_quote("小红书封面", urgent=True)["urgent_fee"] == 20


def test_all_itemized_surcharges_and_manual_adjustment():
    quote = calculate_quote(
        "大型背景墙",
        hours_until_deadline=10,
        source_file_required=True,
        print_required=True,
        complex_cutout=True,
        overall_redesign=True,
        oversized=True,
        manual_adjustment=-9,
    )
    assert quote["base_price"] == 99
    assert quote["urgent_fee"] == 40
    assert quote["source_file_fee"] == 30
    assert quote["print_fee"] == 20
    assert quote["complex_cutout_fee"] == 20
    assert quote["redesign_fee"] == 30
    assert quote["oversized_fee"] == 30
    assert quote["complexity_fee"] == 80
    assert quote["final_price"] == 260


def test_final_price_cannot_be_negative():
    quote = calculate_quote("PPT美化", manual_adjustment=-999)
    assert quote["final_price"] == 0


def test_unknown_design_type_uses_other_price():
    assert get_base_price("未来新增类型") == 49
