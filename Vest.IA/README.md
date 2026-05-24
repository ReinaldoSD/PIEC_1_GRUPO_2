# Vest.IA 👕🤖 - Gerenciador Inteligente de Guarda-Roupa Pessoal

O **Vest.IA** é uma plataforma web moderna dedicada à digitalização, catalogação e otimização de acervos de moda e vestuário pessoais. O sistema realiza o mapeamento detalhado do guarda-roupa dos usuários por meio do agrupamento estruturado de peças por atributos categóricos essenciais, gerando sugestões automatizadas de looks diários em tempo real.

---

## 🎯 Descrição do Problema e Objetivo
Muitas pessoas têm dificuldade em organizar seus guarda-roupas, esquecem as peças que possuem ou perdem muito tempo decidindo o que vestir diariamente. 

O **Vest.IA** resolve o "esquecimento crônico de peças" combinando **Inteligência Artificial local** (visão computacional multimodal) com **telemetria climática em tempo real**, combatendo o desperdício, otimizando o acerto visual e facilitando o gerenciamento do acervo pessoal de vestuário.

---

## ✨ Principais Funcionalidades (Casos de Uso)

1. **Cadastro Inteligente com IA Local:** Upload de fotos de roupas onde um modelo de IA analisa e ajuda na identificação e extração de características das peças (tipo, cor, ocasião, clima ideal).
2. **Listagem e Gestão do Guarda-Roupa:** Catálogo digital completo com filtros avançados por nome, tipo, cor, ocasião e clima ideal, além de funções de edição e exclusão.
3. **Recomendação Baseada no Clima:** Cruzamento de dados da API meteorológica local com as roupas do usuário para gerar combinações ideais divididas em categorias operacionais de moda:
   - **Calor:** Temperaturas elevadas.
   - **Frio:** Temperaturas baixas.
   - **Meia-Estação:** Temperaturas amenas (atua também como mecanismo de resiliência/fallback).
4. **Histórico de Uso Dinâmico:** Registro detalhado de uso de peças individuais, permitindo que o sistema contabilize quantas vezes uma roupa foi usada e destaque as peças esquecidas ou pouco utilizadas.
5. **Autenticação Segura com Validação de E-mail:** Fluxo de cadastro seguro com verificação em duas etapas via protocolo SMTP/TLS, disparando um token numérico de 6 dígitos `[100000, 999999]` para ativação da conta.

---

## 🛠️ Tecnologias e Arquitetura do Sistema

O projeto adota uma arquitetura monolítica modular otimizada para o ecossistema Python com o micro-framework Flask, seguindo o padrão de projeto de software **MVC (Model-View-Controller)**.

* **Back-end & Controllers:** Python 3 + Flask (Gerenciamento de rotas e intermediação lógica).
* **Banco de Dados (Model):** SQLite (Configurado com `PRAGMA journal_mode=WAL` e integridade referencial ativa via `foreign_keys = ON`).
* **Inteligência Artificial (Multimodal Local):** **Fashion-CLIP** carregado via Hugging Face `transformers` e `torch`. Opera localmente de forma offline.
* **API de Clima:** **Open-Meteo API** (Integração assíncrona, leve, sem necessidade de chaves fixas).
* **Front-end (View):** HTML5 semântico estruturado de forma responsiva com **Tailwind CSS** compilado via Jinja2.

### 📂 Organização Lógica do Repositório (Estrutura de Pastas)

```text
VEST.IA (Raiz do Projeto)
│
├── app.py                  # Inicializador central da aplicação e Bootstrapper do Flask
├── routes.py               # Controlador Central (Controller) e Endpoints de API REST
│
├── banco_dados/            # 🗄️ Camada de Persistência e Modelagem (Model / DAO)
│   ├── create_db.py        # DDL - Estruturação e criação das tabelas do banco relacional
│   └── database.py         # DML - Queries, inserções e conexões seguras com SQLite
│
├── templates/              # 🎨 Camada de Visão (View) - Páginas HTML compiladas via Jinja2
│   ├── layout.html         # Estrutura base mestra (Sidebar, Toasts e scripts comuns)
│   ├── login.html          # Interface de autenticação e validação de credenciais
│   ├── register.html       # Formulário de cadastro em duas etapas com segurança 2FA
│   ├── dashboard.html      # Painel administrativo central com indicadores e métricas
│   ├── cadastrar_roupa.html# Tela para upload múltiplo e rotulagem assistida por IA
│   └── minhas_roupas.html  # Catálogo interativo de peças com filtros
│
└── static/                 # 🖼️ Ativos Estáticos (CSS, Imagens do Sistema, Uploads do Usuário)
