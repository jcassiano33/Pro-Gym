import re
from datetime import date

from django.core.exceptions import ValidationError


def somente_digitos(valor):
    return re.sub(r"\D", "", valor or "")


def validate_cpf(value):
    """Valida CPF (aceita com ou sem pontuação) pelo cálculo dos dígitos verificadores."""
    cpf = somente_digitos(value)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        raise ValidationError("CPF inválido.")
    for posicao in (9, 10):
        soma = sum(int(cpf[n]) * (posicao + 1 - n) for n in range(posicao))
        digito = (soma * 10) % 11 % 10
        if digito != int(cpf[posicao]):
            raise ValidationError("CPF inválido.")


def validate_nome(value):
    """Nomes só com letras, espaços, hífen e apóstrofo."""
    limpo = (value or "").replace(" ", "").replace("-", "").replace("'", "")
    if not limpo.isalpha():
        raise ValidationError("Use apenas letras e espaços.")


def validate_telefone(value):
    """Telefone brasileiro com DDD (10 a 13 dígitos, aceitando o prefixo 55)."""
    digitos = somente_digitos(value)
    if not 10 <= len(digitos) <= 13:
        raise ValidationError("Informe o telefone com DDD, ex.: (84) 99999-9999.")


def validate_data_nascimento(value):
    if value > date.today():
        raise ValidationError("A data de nascimento não pode estar no futuro.")
    if value.year < 1900:
        raise ValidationError("Data de nascimento inválida.")
