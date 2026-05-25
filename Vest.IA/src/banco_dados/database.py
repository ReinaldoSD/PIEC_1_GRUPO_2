import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

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

def cadastrar_roupa(usuario_id, nome, tipo, cor, ocasiao, clima, caminhos_fotos):
    """Insere uma nova roupa vinculando-a obrigatoriamente ao ID do usuário logado."""
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO roupas (usuario_id, nome, tipo, cor, ocasiao, clima_ideal, vezes_usada)
        VALUES (?, ?, ?, ?, ?, ?, 0)
    """, (usuario_id, nome, tipo, cor, ocasiao, clima))
    
    roupa_id = cursor.lastrowid

    for caminho in caminhos_fotos:
        cursor.execute("""
            INSERT INTO fotos_roupas (roupa_id, caminho)
            VALUES (?, ?)
        """, (roupa_id, caminho))

    conn.commit()
    conn.close()

def excluir_roupa(roupa_id, usuario_id):
    """Apaga a roupa apenas se ela pertencer ao usuário logado (Segurança contra invasão)."""
    conn = conectar()
    cursor = conn.cursor()

    # Verifica se a peça pertence ao usuário
    cursor.execute("SELECT nome FROM roupas WHERE id = ? AND usuario_id = ?", (roupa_id, usuario_id))
    resultado = cursor.fetchone()
    
    if not resultado:
        conn.close()
        return None 

    nome = resultado['nome']

    # Apaga em cascata por causa das chaves estrangeiras
    cursor.execute("DELETE FROM fotos_roupas WHERE roupa_id = ?", (roupa_id,))
    cursor.execute("DELETE FROM historico WHERE roupa_id = ?", (roupa_id,))
    cursor.execute("DELETE FROM roupas WHERE id = ? AND usuario_id = ?", (roupa_id, usuario_id))

    conn.commit()
    conn.close()
    return nome

def editar_roupa(roupa_id, usuario_id, nome, tipo, cor, ocasiao, clima):
    """Atualiza os dados de uma roupa existente se ela pertencer ao usuário."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE roupas 
        SET nome = ?, tipo = ?, cor = ?, ocasiao = ?, clima_ideal = ?
        WHERE id = ? AND usuario_id = ?
    """, (nome, tipo, cor, ocasiao, clima, roupa_id, usuario_id))
    conn.commit()
    conn.close()

def cadastrar_usuario(nome, email, senha):
    """Insere um novo usuário aplicando hash na password."""
    conn = conectar()
    cursor = conn.cursor()
    
    # Gera um hash seguro a partir da password em texto limpo
    senha_com_hash = generate_password_hash(senha)
    
    try:
        cursor.execute("""
            INSERT INTO usuarios (nome, email, senha)
            VALUES (?, ?, ?)
        """, (nome, email, senha_com_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verificar_usuario(email, senha):
    """Verifica se o e-mail existe e se o hash da password coincide."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, email, senha FROM usuarios WHERE email = ?", (email,))
    usuario = cursor.fetchone()
    conn.close()

    if usuario:
        if check_password_hash(usuario['senha'], senha):
            return dict(usuario)
    return None

def email_existe(email):
    """Verifica se um e-mail já está cadastrado no banco de dados."""
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE email = ?", (email,))
    resultado = cursor.fetchone()
    conn.close()
    
    # Retorna True se achou o e-mail, ou False se não achou
    return resultado is not None

def buscar_historico_usuario(usuario_id):
    """Busca o histórico de uso de roupas apenas do usuário logado."""
    conn = conectar()
    cursor = conn.cursor()
    
    # Fazemos um JOIN entre historico e roupas para filtrar pelo usuario_id
    cursor.execute("""
        SELECT h.id, h.data_uso, r.nome, r.tipo, r.cor, f.caminho as foto
        FROM historico h
        JOIN roupas r ON h.roupa_id = r.id
        LEFT JOIN fotos_roupas f ON r.id = f.roupa_id
        WHERE r.usuario_id = ?
        GROUP BY h.id
        ORDER BY h.data_uso DESC
    """, (usuario_id,))
    
    historico = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return historico
