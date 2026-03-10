import random
import time
import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError, SpreadsheetNotFound

# ==========================================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================================
st.set_page_config(page_title="SERENO FC", layout="wide")

# ==========================================================
# CONFIGURAÇÕES GERAIS
# ==========================================================
INFO_CREDENCIAIS = dict(st.secrets["gcp_service_account"])
NOME_PLANILHA = "FUTEBOL_SERENO"

ABA_CADASTRO = "CADASTRO_JOGADORES"
ABA_PRESENCA = "LISTA_PRESENCA"
ABA_SORTEIO = "LISTA_SORTEIO"

COLUNAS_CADASTRO = ["NOME", "MENSALISTA", "DIARISTA", "CONVIDADO", "PEQUENO_JOGADOR"]
COLUNAS_PRESENCA = ["NOME", "PRESENCA"]
COLUNAS_SORTEIO = ["ORDEM", "TIME_1", "TIME_2"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# ==========================================================
# ACESSO ADMINISTRADOR
# ==========================================================
ADMIN_USUARIO = "Administrador"
ADMIN_SENHA = "Administrador@123"

# ==========================================================
# UTILITÁRIOS DE RESILIÊNCIA
# ==========================================================
def executar_com_retry(func, *args, **kwargs):
    tentativas = 5
    espera_inicial = 1.5

    for tentativa in range(tentativas):
        try:
            return func(*args, **kwargs)
        except APIError as e:
            erro_str = str(e)
            if "429" in erro_str or "RESOURCE_EXHAUSTED" in erro_str:
                if tentativa < tentativas - 1:
                    espera = espera_inicial * (2 ** tentativa)
                    time.sleep(espera)
                    continue
            raise

# ==========================================================
# CONEXÃO
# ==========================================================
@st.cache_resource
def conectar_gsheet():
    creds = Credentials.from_service_account_info(
        INFO_CREDENCIAIS,
        scopes=SCOPES
    )
    client = gspread.authorize(creds)
    planilha = executar_com_retry(client.open, NOME_PLANILHA)

    worksheets = executar_com_retry(planilha.worksheets)
    mapa_abas = {ws.title: ws for ws in worksheets}

    return planilha, mapa_abas

def obter_worksheet(mapa_abas, nome_aba):
    if nome_aba not in mapa_abas:
        raise ValueError(f"A aba '{nome_aba}' não foi encontrada na planilha.")
    return mapa_abas[nome_aba]

def limpar_cache_planilha():
    conectar_gsheet.clear()

# ==========================================================
# FUNÇÕES DE LEITURA/ESCRITA
# ==========================================================
def ler_aba_com_cabecalho(mapa_abas, nome_aba, colunas_esperadas):
    ws = obter_worksheet(mapa_abas, nome_aba)
    valores = executar_com_retry(ws.get_all_values)

    if not valores:
        return pd.DataFrame(columns=colunas_esperadas)

    cabecalho = valores[0]
    linhas = valores[1:]

    if not cabecalho:
        return pd.DataFrame(columns=colunas_esperadas)

    if not linhas:
        return pd.DataFrame(columns=colunas_esperadas)

    linhas_ajustadas = []
    total_colunas = len(cabecalho)

    for linha in linhas:
        linha = list(linha)
        if len(linha) < total_colunas:
            linha.extend([""] * (total_colunas - len(linha)))
        elif len(linha) > total_colunas:
            linha = linha[:total_colunas]
        linhas_ajustadas.append(linha)

    df = pd.DataFrame(linhas_ajustadas, columns=cabecalho)

    for col in colunas_esperadas:
        if col not in df.columns:
            df[col] = ""

    df = df[colunas_esperadas].fillna("")
    return df

def escrever_dataframe_na_aba(mapa_abas, nome_aba, df, colunas_esperadas):
    ws = obter_worksheet(mapa_abas, nome_aba)

    df = df.copy()

    for col in colunas_esperadas:
        if col not in df.columns:
            df[col] = ""

    df = df[colunas_esperadas].fillna("")
    valores = [colunas_esperadas] + df.astype(str).values.tolist()

    executar_com_retry(ws.clear)
    executar_com_retry(ws.update, "A1", valores)

def inicializar_abas_se_necessario(mapa_abas):
    configuracoes = [
        (ABA_CADASTRO, COLUNAS_CADASTRO),
        (ABA_PRESENCA, COLUNAS_PRESENCA),
        (ABA_SORTEIO, COLUNAS_SORTEIO),
    ]

    for nome_aba, colunas in configuracoes:
        ws = obter_worksheet(mapa_abas, nome_aba)
        valores = executar_com_retry(ws.get_all_values)

        if not valores:
            executar_com_retry(ws.update, "A1", [colunas])
        else:
            cabecalho_atual = valores[0]
            if cabecalho_atual != colunas:
                dados_existentes = valores[1:] if len(valores) > 1 else []
                novos_valores = [colunas]

                for linha in dados_existentes:
                    linha = list(linha)
                    if len(linha) < len(colunas):
                        linha.extend([""] * (len(colunas) - len(linha)))
                    elif len(linha) > len(colunas):
                        linha = linha[:len(colunas)]
                    novos_valores.append(linha)

                executar_com_retry(ws.clear)
                executar_com_retry(ws.update, "A1", novos_valores)

# ==========================================================
# FUNÇÕES DE NEGÓCIO
# ==========================================================
def normalizar_nome(nome):
    return str(nome).strip()

def montar_linha_cadastro(nome, categoria):
    return {
        "NOME": nome,
        "MENSALISTA": "SIM" if categoria == "MENSALISTA" else "NÃO",
        "DIARISTA": "SIM" if categoria == "DIARISTA" else "NÃO",
        "CONVIDADO": "SIM" if categoria == "CONVIDADO" else "NÃO",
        "PEQUENO_JOGADOR": "SIM" if categoria == "PEQUENO_JOGADOR" else "NÃO",
    }

def descobrir_categoria_jogador(linha):
    if str(linha.get("MENSALISTA", "")).upper() == "SIM":
        return "MENSALISTA"
    if str(linha.get("DIARISTA", "")).upper() == "SIM":
        return "DIARISTA"
    if str(linha.get("CONVIDADO", "")).upper() == "SIM":
        return "CONVIDADO"
    if str(linha.get("PEQUENO_JOGADOR", "")).upper() == "SIM":
        return "PEQUENO_JOGADOR"
    return ""

def sincronizar_lista_presenca(mapa_abas):
    df_cadastro = ler_aba_com_cabecalho(mapa_abas, ABA_CADASTRO, COLUNAS_CADASTRO)
    df_presenca = ler_aba_com_cabecalho(mapa_abas, ABA_PRESENCA, COLUNAS_PRESENCA)

    nomes_cadastro = [
        normalizar_nome(x) for x in df_cadastro["NOME"].tolist()
        if normalizar_nome(x)
    ]

    presenca_atual = {}
    for _, row in df_presenca.iterrows():
        nome = normalizar_nome(row["NOME"])
        if nome:
            presenca_atual[nome] = str(row["PRESENCA"]).upper().strip() or "NÃO"

    novas_linhas = []
    for nome in nomes_cadastro:
        novas_linhas.append({
            "NOME": nome,
            "PRESENCA": presenca_atual.get(nome, "NÃO")
        })

    novo_df_presenca = pd.DataFrame(novas_linhas, columns=COLUNAS_PRESENCA)
    escrever_dataframe_na_aba(mapa_abas, ABA_PRESENCA, novo_df_presenca, COLUNAS_PRESENCA)

def sortear_times(df_cadastro, df_presenca):
    cadastro_map = {}
    for _, row in df_cadastro.iterrows():
        nome = normalizar_nome(row["NOME"])
        if nome:
            cadastro_map[nome] = {
                "categoria": descobrir_categoria_jogador(row.to_dict())
            }

    presentes = []
    for _, row in df_presenca.iterrows():
        nome = normalizar_nome(row["NOME"])
        presenca = str(row["PRESENCA"]).upper().strip()
        if nome and presenca == "SIM" and nome in cadastro_map:
            presentes.append({
                "nome": nome,
                "categoria": cadastro_map[nome]["categoria"]
            })

    grupos = {
        "MENSALISTA": [],
        "DIARISTA": [],
        "CONVIDADO": [],
        "PEQUENO_JOGADOR": []
    }

    for jogador in presentes:
        categoria = jogador["categoria"]
        if categoria in grupos:
            grupos[categoria].append(jogador["nome"])

    for categoria in grupos:
        random.shuffle(grupos[categoria])

    time_1 = []
    time_2 = []
    proximo_time = 1

    def adicionar_jogador(nome_jogador):
        nonlocal proximo_time, time_1, time_2

        if len(time_1) < len(time_2):
            time_1.append(nome_jogador)
            proximo_time = 2
        elif len(time_2) < len(time_1):
            time_2.append(nome_jogador)
            proximo_time = 1
        else:
            if proximo_time == 1:
                time_1.append(nome_jogador)
                proximo_time = 2
            else:
                time_2.append(nome_jogador)
                proximo_time = 1

    ordem_categorias = ["MENSALISTA", "DIARISTA", "CONVIDADO", "PEQUENO_JOGADOR"]

    for categoria in ordem_categorias:
        for nome_jogador in grupos[categoria]:
            adicionar_jogador(nome_jogador)

    max_len = max(len(time_1), len(time_2), 0)
    linhas_sorteio = []

    for i in range(max_len):
        linhas_sorteio.append({
            "ORDEM": str(i + 1),
            "TIME_1": time_1[i] if i < len(time_1) else "",
            "TIME_2": time_2[i] if i < len(time_2) else "",
        })

    df_sorteio = pd.DataFrame(linhas_sorteio, columns=COLUNAS_SORTEIO)
    return df_sorteio

# ==========================================================
# ESTADO INICIAL
# ==========================================================
if "abas_inicializadas" not in st.session_state:
    st.session_state.abas_inicializadas = False

if "admin_autenticado" not in st.session_state:
    st.session_state.admin_autenticado = False

if "admin_erro_login" not in st.session_state:
    st.session_state.admin_erro_login = ""

# ==========================================================
# SIDEBAR - LOGIN ADMIN
# ==========================================================
with st.sidebar:
    st.header("Acesso administrativo")

    if not st.session_state.admin_autenticado:
        with st.form("form_login_admin"):
            usuario_admin = st.text_input("Usuário")
            senha_admin = st.text_input("Senha", type="password")
            entrar_admin = st.form_submit_button("Entrar como administrador")

        if entrar_admin:
            if usuario_admin == ADMIN_USUARIO and senha_admin == ADMIN_SENHA:
                st.session_state.admin_autenticado = True
                st.session_state.admin_erro_login = ""
                st.rerun()
            else:
                st.session_state.admin_erro_login = "Usuário ou senha inválidos."

        if st.session_state.admin_erro_login:
            st.error(st.session_state.admin_erro_login)

        st.info("Sem login de administrador, o app ficará apenas em modo de visualização.")
    else:
        st.success("Administrador autenticado.")
        st.write(f"Usuário: {ADMIN_USUARIO}")

        if st.button("Sair do modo administrador", use_container_width=True):
            st.session_state.admin_autenticado = False
            st.session_state.admin_erro_login = ""
            st.rerun()

# ==========================================================
# APP
# ==========================================================
st.title("FUTEBOL_SERENO")

try:
    planilha, mapa_abas = conectar_gsheet()

    if not st.session_state.abas_inicializadas:
        inicializar_abas_se_necessario(mapa_abas)
        st.session_state.abas_inicializadas = True

    if st.session_state.admin_autenticado:
        st.success("Modo administrador ativo.")
    else:
        st.info("Modo visualização ativo. Faça login na barra lateral para alterar dados.")

    abas = st.tabs(["CADASTRO DE JOGADORES", "LISTA DE PRESENCA", "SORTEIO DOS TIMES"])

    with abas[0]:
        st.subheader("Cadastro de jogadores")

        df_cadastro = ler_aba_com_cabecalho(mapa_abas, ABA_CADASTRO, COLUNAS_CADASTRO)
        df_cadastro["NOME"] = df_cadastro["NOME"].astype(str).str.strip()
        df_cadastro = df_cadastro[df_cadastro["NOME"] != ""].reset_index(drop=True)

        if st.session_state.admin_autenticado:
            st.markdown("### Adicionar novo jogador")
            with st.form("form_cadastro"):
                nome_jogador = st.text_input("Nome do jogador")
                categoria = st.radio(
                    "Categoria",
                    ["MENSALISTA", "DIARISTA", "CONVIDADO", "PEQUENO_JOGADOR"],
                    horizontal=True
                )
                enviar_cadastro = st.form_submit_button("Salvar jogador")

            if enviar_cadastro:
                nome_jogador = normalizar_nome(nome_jogador)

                if not nome_jogador:
                    st.error("Informe o nome do jogador.")
                elif nome_jogador.upper() in [x.upper() for x in df_cadastro["NOME"].tolist()]:
                    st.error("Esse jogador já está cadastrado.")
                else:
                    nova_linha = montar_linha_cadastro(nome_jogador, categoria)
                    df_cadastro = pd.concat([df_cadastro, pd.DataFrame([nova_linha])], ignore_index=True)
                    df_cadastro = df_cadastro.sort_values(by="NOME").reset_index(drop=True)

                    escrever_dataframe_na_aba(mapa_abas, ABA_CADASTRO, df_cadastro, COLUNAS_CADASTRO)
                    sincronizar_lista_presenca(mapa_abas)

                    limpar_cache_planilha()
                    st.success("Jogador cadastrado com sucesso.")
                    st.rerun()
        else:
            st.warning("Área de edição restrita ao administrador.")

        st.markdown("---")
        st.markdown("### Jogadores cadastrados")

        if df_cadastro.empty:
            st.info("Nenhum jogador cadastrado ainda.")
        else:
            df_exibir = df_cadastro.copy()
            df_exibir["CATEGORIA"] = df_exibir.apply(
                lambda row: descobrir_categoria_jogador(row.to_dict()), axis=1
            )
            st.dataframe(df_exibir[["NOME", "CATEGORIA"]], use_container_width=True, hide_index=True)

            if st.session_state.admin_autenticado:
                st.markdown("### Atualizar categoria de jogador")
                nomes_existentes = df_cadastro["NOME"].tolist()

                with st.form("form_editar"):
                    jogador_editar = st.selectbox("Selecione o jogador", nomes_existentes)
                    categoria_atual = descobrir_categoria_jogador(
                        df_cadastro[df_cadastro["NOME"] == jogador_editar].iloc[0].to_dict()
                    )
                    opcoes_categoria = ["MENSALISTA", "DIARISTA", "CONVIDADO", "PEQUENO_JOGADOR"]
                    indice_atual = opcoes_categoria.index(categoria_atual) if categoria_atual in opcoes_categoria else 0

                    categoria_editar = st.radio(
                        "Nova categoria",
                        opcoes_categoria,
                        index=indice_atual,
                        horizontal=True
                    )
                    salvar_edicao = st.form_submit_button("Atualizar categoria")

                if salvar_edicao:
                    idx = df_cadastro.index[df_cadastro["NOME"] == jogador_editar][0]
                    linha_atualizada = montar_linha_cadastro(jogador_editar, categoria_editar)
                    for col in COLUNAS_CADASTRO:
                        df_cadastro.at[idx, col] = linha_atualizada[col]

                    escrever_dataframe_na_aba(mapa_abas, ABA_CADASTRO, df_cadastro, COLUNAS_CADASTRO)
                    sincronizar_lista_presenca(mapa_abas)

                    limpar_cache_planilha()
                    st.success("Categoria atualizada com sucesso.")
                    st.rerun()

                st.markdown("### Excluir jogador")
                with st.form("form_excluir"):
                    jogador_excluir = st.selectbox(
                        "Selecione o jogador para excluir",
                        nomes_existentes,
                        key="excluir_jogador"
                    )
                    excluir = st.form_submit_button("Excluir jogador")

                if excluir:
                    df_cadastro = df_cadastro[df_cadastro["NOME"] != jogador_excluir].reset_index(drop=True)
                    escrever_dataframe_na_aba(mapa_abas, ABA_CADASTRO, df_cadastro, COLUNAS_CADASTRO)
                    sincronizar_lista_presenca(mapa_abas)

                    limpar_cache_planilha()
                    st.success("Jogador excluído com sucesso.")
                    st.rerun()

    with abas[1]:
        st.subheader("Lista de presença")

        df_presenca = ler_aba_com_cabecalho(mapa_abas, ABA_PRESENCA, COLUNAS_PRESENCA)
        df_presenca["NOME"] = df_presenca["NOME"].astype(str).str.strip()
        df_presenca = df_presenca[df_presenca["NOME"] != ""].reset_index(drop=True)

        if st.session_state.admin_autenticado:
            col1, col2 = st.columns(2)

            with col1:
                if st.button("Sincronizar nomes com cadastro", use_container_width=True):
                    sincronizar_lista_presenca(mapa_abas)
                    limpar_cache_planilha()
                    st.success("Lista de presença sincronizada com o cadastro.")
                    st.rerun()

            with col2:
                if st.button("Marcar todos como NÃO", use_container_width=True):
                    if not df_presenca.empty:
                        df_presenca["PRESENCA"] = "NÃO"
                        escrever_dataframe_na_aba(mapa_abas, ABA_PRESENCA, df_presenca, COLUNAS_PRESENCA)

                    limpar_cache_planilha()
                    st.success("Presenças zeradas com sucesso.")
                    st.rerun()

            if df_presenca.empty:
                st.info("Nenhum jogador disponível na lista de presença. Cadastre jogadores na aba CADASTRO DE JOGADORES.")
            else:
                with st.form("form_presenca"):
                    novos_valores = []

                    for i, row in df_presenca.iterrows():
                        nome = row["NOME"]
                        valor_atual = str(row["PRESENCA"]).upper().strip() == "SIM"

                        marcado = st.checkbox(nome, value=valor_atual, key=f"presenca_{i}")
                        novos_valores.append({
                            "NOME": nome,
                            "PRESENCA": "SIM" if marcado else "NÃO"
                        })

                    salvar_presenca = st.form_submit_button("Salvar presença")

                if salvar_presenca:
                    novo_df_presenca = pd.DataFrame(novos_valores, columns=COLUNAS_PRESENCA)
                    escrever_dataframe_na_aba(mapa_abas, ABA_PRESENCA, novo_df_presenca, COLUNAS_PRESENCA)

                    limpar_cache_planilha()
                    st.success("Lista de presença salva com sucesso.")
                    st.rerun()
        else:
            st.warning("Alterações de presença restritas ao administrador.")

        st.markdown("### Presenças atuais")
        if df_presenca.empty:
            st.info("Nenhum jogador disponível na lista de presença.")
        else:
            st.dataframe(df_presenca, use_container_width=True, hide_index=True)

    with abas[2]:
        st.subheader("Sorteio dos times")

        if st.session_state.admin_autenticado:
            col1, col2 = st.columns(2)

            with col1:
                if st.button("Sortear times", use_container_width=True):
                    df_cadastro = ler_aba_com_cabecalho(mapa_abas, ABA_CADASTRO, COLUNAS_CADASTRO)
                    df_presenca = ler_aba_com_cabecalho(mapa_abas, ABA_PRESENCA, COLUNAS_PRESENCA)

                    df_cadastro["NOME"] = df_cadastro["NOME"].astype(str).str.strip()
                    df_presenca["NOME"] = df_presenca["NOME"].astype(str).str.strip()

                    df_cadastro = df_cadastro[df_cadastro["NOME"] != ""].reset_index(drop=True)
                    df_presenca = df_presenca[df_presenca["NOME"] != ""].reset_index(drop=True)

                    presentes_sim = df_presenca[
                        df_presenca["PRESENCA"].astype(str).str.upper().str.strip() == "SIM"
                    ]

                    if df_cadastro.empty:
                        st.error("Não há jogadores cadastrados.")
                    elif df_presenca.empty:
                        st.error("A lista de presença está vazia.")
                    elif presentes_sim.empty:
                        st.error("Nenhum jogador foi marcado como presente.")
                    else:
                        df_sorteio = sortear_times(df_cadastro, df_presenca)
                        escrever_dataframe_na_aba(mapa_abas, ABA_SORTEIO, df_sorteio, COLUNAS_SORTEIO)

                        limpar_cache_planilha()
                        st.success("Sorteio realizado com sucesso.")
                        st.rerun()

            with col2:
                if st.button("Limpar sorteio", use_container_width=True):
                    df_vazio = pd.DataFrame(columns=COLUNAS_SORTEIO)
                    escrever_dataframe_na_aba(mapa_abas, ABA_SORTEIO, df_vazio, COLUNAS_SORTEIO)

                    limpar_cache_planilha()
                    st.success("Sorteio limpo com sucesso.")
                    st.rerun()
        else:
            st.warning("Sortear e limpar sorteio são ações restritas ao administrador.")

        df_sorteio = ler_aba_com_cabecalho(mapa_abas, ABA_SORTEIO, COLUNAS_SORTEIO)
        df_sorteio["ORDEM"] = df_sorteio["ORDEM"].astype(str).str.strip()
        df_sorteio = df_sorteio[df_sorteio["ORDEM"] != ""].reset_index(drop=True)

        if df_sorteio.empty:
            st.info("Ainda não há sorteio realizado.")
        else:
            st.markdown("### Resultado do sorteio")
            st.dataframe(df_sorteio, use_container_width=True, hide_index=True)

            qtd_time_1 = (df_sorteio["TIME_1"].astype(str).str.strip() != "").sum()
            qtd_time_2 = (df_sorteio["TIME_2"].astype(str).str.strip() != "").sum()

            c1, c2 = st.columns(2)
            c1.metric("Jogadores no TIME_1", int(qtd_time_1))
            c2.metric("Jogadores no TIME_2", int(qtd_time_2))

except SpreadsheetNotFound:
    st.error("Planilha 'FUTEBOL_SERENO' não encontrada ou não compartilhada com a service account.")
except Exception as e:
    st.error("Erro ao executar a aplicação.")
    st.exception(e)
