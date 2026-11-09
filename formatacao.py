"""Apresentação numérica em português, independente das camadas do app."""
import math


def numero(valor, casas=1):
    if valor is None or not math.isfinite(float(valor)):
        return "—"
    return f"{valor:,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def percentual(valor, casas=1):
    texto = numero(valor, casas)
    return texto + "%" if texto != "—" else texto
