"""Cálculo da prescrição nutricional. Fator, meta e escolhas são sempre do Erik."""
from calc import br


def mil(n):
    return f"{int(round(n)):,}".replace(",", ".")


def rer(peso):
    return 70 * peso ** 0.75


def energia(peso, fator=None, der=None):
    r = rer(peso)
    d = der if der else r * fator
    memoria = [f"RER = 70 × {br(peso)}^0,75 = {br(r, 1)} kcal"]
    memoria.append(f"DER = {br(r, 1)} × {br(fator)} = {br(d, 1)} kcal/dia" if not der else f"DER definido pelo Erik: {br(d, 1)} kcal/dia")
    return r, d, memoria


def opcoes(der, refeicoes, seca, umida, pct_seca_mix=0.9):
    """seca/umida: dicts do catálogo (ou None). Devolve linhas da tabela e memória."""
    linhas, mem = [], []
    if seca:
        g = der / seca["kcal_kg"] * 1000
        linhas.append({"tipo": "seca", "rotulo": "Seca pura", "comp": f"{seca['nome']} · {mil(seca['kcal_kg'])} kcal/kg",
                       "sub": f"Embalagens: {seca['embalagens']}", "dia": f"{round(g)} g", "ref": f"{round(g / refeicoes)} g"})
        mem.append(f"seca: {br(der, 1)} ÷ {br(seca['kcal_kg'] / 1000, 3)} kcal/g = {br(g, 1)} g/dia")
    if seca and umida:
        gs = der * pct_seca_mix / seca["kcal_kg"] * 1000
        gu = der * (1 - pct_seca_mix) / umida["kcal_kg"] * 1000
        p = round(pct_seca_mix * 100)
        linhas.append({"tipo": "mix", "rotulo": "Mix seca + úmida", "comp": f"{p}% seca + {100 - p}% úmida (em calorias), mesma tigela",
                       "sub": "Combina os dois formatos", "dia": f"{round(gs)} g seca + {round(gu)} g úmida",
                       "ref": f"{round(gs / refeicoes)} g + {round(gu / refeicoes)} g"})
        mem.append(f"mix: {p}% de {br(der, 1)} = {br(der * pct_seca_mix, 1)} kcal → {br(gs, 1)} g seca; {100 - p}% = {br(der * (1 - pct_seca_mix), 1)} kcal → {br(gu, 1)} g úmida")
    if umida:
        g = der / umida["kcal_kg"] * 1000
        sub = f"Embalagens: {umida['embalagens']}"
        if umida.get("g_por_unidade"):
            sub = f"≈ {br(g / umida['g_por_unidade'], 2)} {umida.get('unidade', 'unidade')}/dia · {umida['embalagens']}"
        linhas.append({"tipo": "umida", "rotulo": "Úmida pura", "comp": f"{umida['nome']} · {mil(umida['kcal_kg'])} kcal/kg",
                       "sub": sub, "dia": f"{round(g)} g", "ref": f"{round(g / refeicoes)} g"})
        mem.append(f"úmida: {br(der, 1)} ÷ {br(umida['kcal_kg'] / 1000, 3)} kcal/g = {br(g, 1)} g/dia")
    return linhas, mem
