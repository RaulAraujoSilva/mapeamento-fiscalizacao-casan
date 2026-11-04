"""Portão de publicação: nenhuma saída versionada (saida/, docs/) pode trazer nome de usuário, endereço, CPF,
e-mail ou telefone de terceiros citados nas peças do SEI. Se falhar, rode `python scripts/sanear_saida.py`."""
import sanear_saida as ss


def test_saidas_sem_dados_pessoais():
    restos = {}
    for p in ss.arquivos():
        if p.suffix == ".xlsx":
            continue  # conferida pelo script (--verificar); aqui só os textos, para o teste ficar rápido
        texto, _ = ss._ler(p)
        achou = ss.achados_arquivo(texto, p.suffix)
        if achou:
            restos[p.relative_to(ss.RAIZ).as_posix()] = achou[:3]
    assert not restos, f"dados pessoais nas saídas (rode scripts/sanear_saida.py): {restos}"


def test_exemplos_e_cdn_nao_sao_dado_pessoal():
    assert not ss.achados("pacote bpmn-js@17.11.1 e fonte wght@6..72")
    assert not [x for x in ss.achados("escreva para seu.email@exemplo.edu.br") if not ss.EXEMPLO.search(x)]
    assert not ss.achados("Sr. Conselheiro Relator e Consumidor Amplo Especial")
    assert not ss.achados("processo 100043-2018 da RUA X E ALAMEDA Y - 26/03/2022")
    assert ss.achados("a usuária Maria Souza, Rua das Flores, nº 12, tel. (21) 99876-5432")
