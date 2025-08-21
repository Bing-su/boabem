import pytest

from boabem import Context


def is_intl_supported() -> bool:
    ctx = Context()
    return ctx.eval("typeof Intl !== 'undefined'")


pytestmark = pytest.mark.skipif(
    not is_intl_supported(), reason="Intl not supported in this runtime"
)


def test_intl_number_format_basic_grouping():
    ctx = Context()
    formatted = ctx.eval("new Intl.NumberFormat('en-US').format(1234567.89)")
    assert formatted == "1,234,567.89"


def test_intl_collator_compare_and_sort_sign():
    ctx = Context()
    cmp_ab = ctx.eval("new Intl.Collator('en').compare('a','b')")
    cmp_ba = ctx.eval("new Intl.Collator('en').compare('b','a')")
    cmp_aa = ctx.eval("new Intl.Collator('en').compare('a','a')")
    assert cmp_ab < 0
    assert cmp_ba > 0
    assert cmp_aa == 0


def test_intl_plural_rules_en_basic():
    ctx = Context()
    one = ctx.eval("new Intl.PluralRules('en-US').select(1)")
    other = ctx.eval("new Intl.PluralRules('en-US').select(2)")
    zero = ctx.eval("new Intl.PluralRules('en-US').select(0)")
    assert one == "one"
    assert other == "other"
    assert zero == "other"


def test_intl_listformat_conjunction_en():
    ctx = Context()
    formatted = ctx.eval(
        "new Intl.ListFormat('en', { style: 'long', type: 'conjunction' }).format(['A','B','C'])",
    )
    assert formatted == "A, B, and C"


def test_intl_get_canonical_locales_and_supported_locales():
    ctx = Context()
    canon = ctx.eval("Intl.getCanonicalLocales('EN-us')[0]")
    assert canon == "en-US"
    supported_len = ctx.eval("Intl.NumberFormat.supportedLocalesOf(['en-US']).length")
    assert supported_len == 1
