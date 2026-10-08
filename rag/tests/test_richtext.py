"""Code and math are protected from citation handling, and rendered safely."""
from django.test import SimpleTestCase

from rag.citations import validate
from rag.render import markdown_to_safe_html, render_partial
from rag.segments import CODE, MATH, PROSE, normalize_math, split

DIAGNOSIS = (
    'É \\(O(n \\log n)\\) e $f(x)=x^2$ [1]. Custa R$ 10 e R$ 20.\n\n'
    '```python\ndef troco(moedas, v):\n    dp = [0] + [10**9] * v\n    return dp[v] if dp[3] else moedas[1, 2]\n```\n'
    'Use `arr[2]` aqui [1].'
)


class SegmentTests(SimpleTestCase):
    def test_split_is_lossless_and_classifies(self):
        segs = split(DIAGNOSIS)
        self.assertEqual(''.join(s.text for s in segs), DIAGNOSIS)
        kinds = [s.kind for s in segs]
        self.assertIn(CODE, kinds)
        self.assertEqual([s.tex for s in segs if s.kind == MATH], ['O(n \\log n)', 'f(x)=x^2'])

    def test_money_is_not_math(self):
        self.assertEqual([s.kind for s in split('Custa R$ 10 e R$ 20.')], [PROSE])

    def test_unclosed_fence_is_code(self):
        segs = split('Veja:\n```py\nx = [1]\n')
        self.assertEqual(segs[-1].kind, CODE)

    def test_escaped_dollar_stays_prose(self):
        self.assertEqual([s.kind for s in split('Preço \\$5 apenas')], [PROSE])

    def test_normalize_brackets_to_dollars(self):
        self.assertEqual(normalize_math('a \\(x\\) b'), 'a $x$ b')
        self.assertIn('$$\ny\n$$', normalize_math('\\[y\\]'))


class GateProtectsCodeTests(SimpleTestCase):
    def test_diagnosis_case_code_is_untouched(self):
        result = validate(DIAGNOSIS, {1})
        self.assertIn('    dp = [0] + [10**9] * v', result.text)  # indentation and [0] kept
        self.assertIn('return dp[v] if dp[3] else moedas[1, 2]', result.text)
        self.assertIn('`arr[2]`', result.text)
        self.assertEqual(result.cited, {1})
        self.assertEqual(result.removed, frozenset())

    def test_prose_citations_are_still_validated(self):
        result = validate('Certo [1]. Errado [7].\n\n```\nx[7]\n```', {1})
        self.assertIn('Errado.', result.text)
        self.assertIn('x[7]', result.text)
        self.assertEqual(result.removed, {7})

    def test_nested_list_indentation_survives(self):
        text = '- item [1]\n    - sub [9]\n        - deeper'
        self.assertEqual(validate(text, {1}).text, '- item [1]\n    - sub\n        - deeper')


class RenderTests(SimpleTestCase):
    def test_math_becomes_escaped_math_elements(self):
        html = markdown_to_safe_html('Inline $x^2$ e bloco:\n\n$$\\sum i$$\n\nE \\(y\\).')
        self.assertIn('<span class="math inline">x^2</span>', html)
        self.assertIn('<div class="math block">', html)
        self.assertIn('<span class="math inline">y</span>', html)

    def test_math_cannot_inject_html(self):
        html = markdown_to_safe_html('$<img src=x onerror=alert(1)>$')
        self.assertNotIn('<img', html)
        self.assertIn('&lt;img', html)

    def test_code_is_highlighted_and_keeps_indentation(self):
        html = markdown_to_safe_html('```python\ndef f():\n    return [0]\n```')
        self.assertIn('<code class="language-python">', html)
        self.assertIn('class="tok-k"', html)
        self.assertIn('\n    <span class="tok-k">return</span>', html)

    def test_only_known_classes_survive(self):
        html = markdown_to_safe_html('```unknown-lang\nx\n```')
        self.assertNotIn('class="evil"', html)
        # nh3 drops any class our renderer did not produce
        from rag.render import _class_filter
        self.assertIsNone(_class_filter('span', 'class', 'evil'))
        self.assertIsNone(_class_filter('div', 'class', 'c-citation'))
        self.assertEqual(_class_filter('span', 'class', 'tok-nf'), 'tok-nf')

    def test_no_citation_chip_inside_code(self):
        html = render_partial('Fato [1].\n\n```python\nx = a[1]\n```\nUse `b[2]`.')
        self.assertEqual(html.count('c-citation--pending'), 1)
        self.assertIn('<code>b[2]</code>', html)

    def test_tables_render(self):
        self.assertIn('<td>1</td>', markdown_to_safe_html('| a |\n|---|\n| 1 |'))
