import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))

from app import app
from modulos.ia_sugestoes import MAPA_OCASIAO

# ─── Configuração do Ambiente de Testes ────────────────────
@pytest.fixture
def cliente():
    """Configura o cliente de testes do Flask para simular pedidos."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# ─── 1. Testes de Integração e Segurança (Rotas) ───────────
def test_pagina_login_status(cliente):
    """
    Verifica se a página pública de login carrega corretamente.
    Deve retornar o código HTTP 200 (OK).
    """
    resposta = cliente.get('/login')
    assert resposta.status_code == 200
    assert b'Login' in resposta.data  # Verifica se o HTML renderizou o formulário

def test_seguranca_dashboard_sem_login(cliente):
    """
    Testa a segurança das rotas protegidas pelo decorador @login_obrigatorio.
    Um utilizador anónimo deve ser bloqueado e redirecionado (HTTP 302).
    """
    resposta = cliente.get('/dashboard')
    assert resposta.status_code == 302

# ─── 2. Testes Unitários (Regras de Negócio da IA) ─────────
def test_regras_de_ocasiao_ia():
    """
    Testa a heurística do dicionário que mapeia as intenções do utilizador 
    para as categorias que o modelo Fashion-CLIP compreende.
    """
    # Testes de casos de sucesso esperados
    assert MAPA_OCASIAO.get('casamento') == 'Formal'
    assert MAPA_OCASIAO.get('academia') == 'Esporte'
    assert MAPA_OCASIAO.get('shopping') == 'Casual'
    assert MAPA_OCASIAO.get('reuniao') == 'Trabalho'
    
    # Teste de um caso negativo (palavra que a IA não conhece)
    assert MAPA_OCASIAO.get('palavra_inexistente') is None