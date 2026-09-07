"""Receitas da demo online (SQL, DAX, M)."""

from __future__ import annotations

DEMO_DAX_EXAMPLE = (
    'Faixa Valor = IF([valor_linha] > 5000, "Alto", IF([valor_linha] > 1000, "Medio", "Baixo"))'
)

DEMO_M_EXAMPLE = """Pagas = Table.SelectRows(vendas_demo, each [status] = "pago"),
Colunas = Table.SelectColumns(
    Pagas,
    {"produto", "regiao", "valor_linha", "data_venda"}
),
"""


def demo_sql_recipes(*, vendas: str = "vendas_demo", clientes: str = "clientes_demo") -> str:
    """Exemplos SQL alinhados aos datasets de demo."""
    return f"""-- Top produtos por faturamento
SELECT produto, SUM(valor_linha) AS total
FROM "{vendas}"
WHERE status = 'pago'
GROUP BY 1
ORDER BY 2 DESC
LIMIT 10;

-- Vendas por região e canal
SELECT regiao, canal, COUNT(*) AS pedidos, ROUND(SUM(valor_linha), 2) AS total
FROM "{vendas}"
GROUP BY 1, 2
ORDER BY 4 DESC;

-- JOIN com clientes (segmento)
SELECT c.segmento, COUNT(*) AS pedidos, ROUND(SUM(v.valor_linha), 2) AS total
FROM "{vendas}" v
JOIN "{clientes}" c ON v.cliente_id = c.cliente_id
WHERE v.status = 'pago'
GROUP BY 1
ORDER BY 3 DESC;
"""


def render_demo_recipes_panel(*, show_heading: bool = True, compact: bool = False) -> None:
    """Painel de receitas (empty state / dica cloud).

    ``compact=True`` evita expanders aninhados (útil dentro de outro expander).
    """
    import streamlit as st

    if show_heading:
        st.markdown("#### Receitas rápidas")
        st.caption("Copie para a aba SQL, Colunas (DAX) ou o tradutor M.")

    if compact:
        st.markdown("**SQL**")
        st.code(demo_sql_recipes(), language="sql")
        st.markdown("**DAX** (aba Colunas → Power BI)")
        st.code(DEMO_DAX_EXAMPLE, language="text")
        st.markdown("**Power Query M** (aba SQL → tradutor M)")
        st.code(DEMO_M_EXAMPLE, language="text")
        return

    with st.expander("SQL — top produtos, região e JOIN", expanded=False):
        st.code(demo_sql_recipes(), language="sql")
    with st.expander("DAX — coluna calculada", expanded=False):
        st.code(DEMO_DAX_EXAMPLE, language="text")
        st.caption("Na aba **Colunas** → Power BI (DAX).")
    with st.expander("Power Query (M) — filtrar e selecionar colunas", expanded=False):
        st.code(DEMO_M_EXAMPLE, language="text")
        st.caption("Na aba **SQL** → expander do tradutor M.")
