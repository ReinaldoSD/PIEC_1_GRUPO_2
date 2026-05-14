import sqlite3

def criar_banco():
    """Cria o arquivo do banco de dados e as tabelas necessárias."""
    conn = sqlite3.connect('vest_ia.db')
    cursor = conn.cursor()

    # Tabela de Usuários (Mantida para compatibilidade, mesmo sem uso obrigatório)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL
    )
    """)

    # Tabela de Roupas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS roupas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        tipo TEXT,
        cor TEXT,
        ocasiao TEXT,
        clima_ideal TEXT,
        vezes_usada INTEGER DEFAULT 0
    )
    """)

    # Tabela de Fotos (Uma roupa pode ter várias fotos)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fotos_roupas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roupa_id INTEGER NOT NULL,
        caminho TEXT NOT NULL,
        FOREIGN KEY (roupa_id) REFERENCES roupas (id)
    )
    """)

    # Tabela de Histórico de Uso
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roupa_id INTEGER NOT NULL,
        data_uso TEXT NOT NULL,
        FOREIGN KEY (roupa_id) REFERENCES roupas (id)
    )
    """)

    conn.commit()
    conn.close()
    print("Banco de dados e tabelas verificados/criados com sucesso!")

if __name__ == "__main__":
    criar_banco()