import sqlite3
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
DB_FOLDER = os.path.join(project_root, 'banco_dados')
DB_PATH = os.path.join(DB_FOLDER, 'vest.ia.db')

def conectar():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    
    conn.execute("PRAGMA journal_mode=WAL") 
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

def cadastrar_roupa(nome, tipo, cor, ocasiao, clima, caminhos_fotos):
    """Insere uma nova roupa e suas respectivas fotos no banco."""
    conn = conectar()
    cursor = conn.cursor()

    # Inserir a roupa
    cursor.execute("""
        INSERT INTO roupas (nome, tipo, cor, ocasiao, clima_ideal, vezes_usada)
        VALUES (?, ?, ?, ?, ?, 0)
    """, (nome, tipo, cor, ocasiao, clima))
    
    roupa_id = cursor.lastrowid

    # Inserir as fotos relacionadas
    for caminho in caminhos_fotos:
        cursor.execute("""
            INSERT INTO fotos_roupas (roupa_id, caminho)
            VALUES (?, ?)
        """, (roupa_id, caminho))

    conn.commit()
    conn.close()

def excluir_roupa(roupa_id):
    """Exclui a roupa e retorna o nome da peça para confirmação."""
    conn = conectar()
    cursor = conn.cursor()

    # Buscar nome antes de deletar
    cursor.execute("SELECT nome FROM roupas WHERE id = ?", (roupa_id,))
    resultado = cursor.fetchone()
    nome = resultado['nome'] if resultado else "Desconhecido"

    # Deletar (as fotos e histórico podem ser mantidos ou deletados em cascata)
    cursor.execute("DELETE FROM fotos_roupas WHERE roupa_id = ?", (roupa_id,))
    cursor.execute("DELETE FROM historico WHERE roupa_id = ?", (roupa_id,))
    cursor.execute("DELETE FROM roupas WHERE id = ?", (roupa_id,))

    conn.commit()
    conn.close()
    return nome

def editar_roupa(roupa_id, nome, tipo, cor, ocasiao, clima):
    """Atualiza os dados de uma roupa existente."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE roupas 
        SET nome = ?, tipo = ?, cor = ?, ocasiao = ?, clima_ideal = ?
        WHERE id = ?
    """, (nome, tipo, cor, ocasiao, clima, roupa_id))
    conn.commit()
    conn.close()
