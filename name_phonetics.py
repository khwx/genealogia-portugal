"""
Módulo de Normalização Fonética e Variantes Históricas de Nomes Portugueses.

Desenvolvido para genealogia portuguesa (registos paroquiais dos séculos XVI a XX),
permitindo a busca e cruzamento tolerante a grafias arcaicas e variações fonéticas:
- Grafias arcaicas (ex: Joam/João, Manoel/Manuel, Theresa/Teresa, Francysco/Francisco)
- Normalização fonética (Soundex adaptado à língua portuguesa)
- Expansão de consultas para PostgREST / Supabase
- Zero dependências externas (apenas standard library)
"""
import re
import unicodedata
from typing import Dict, List, Set, Tuple


def remove_accents(text: str) -> str:
    """Remove acentos e diacríticos de uma string."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_token(token: str) -> str:
    """Normaliza um token para comparação: minúsculas, sem acentos, sem pontuação."""
    if not token:
        return ""
    cleaned = remove_accents(token).lower().strip()
    return re.sub(r"[^a-z0-9]", "", cleaned)


# Base de clusters de variantes históricas portuguesas
HISTORICAL_CLUSTERS: List[List[str]] = [
    # Nomes masculinos frequentes
    ["João", "Joao", "Joam", "Joan", "Jhoam"],
    ["Manuel", "Manoel", "Emanuel", "Manoell"],
    ["António", "Antonio", "Anttonio", "Antonjo", "Antoni"],
    ["José", "Jose", "Joseph", "Joze", "Josephe"],
    ["Francisco", "Francysco", "Françisco", "Chico"],
    ["Luís", "Luis", "Luiz", "Luys"],
    ["Tomás", "Tomas", "Thomaz", "Thomas", "Thomé", "Tomé"],
    ["Inácio", "Inacio", "Ignacio", "Ignácio", "Ignacia", "Inacia"],
    ["Mateus", "Matheus", "Matteus", "Matheos"],
    ["Vicente", "Vysente", "Bicente", "Vicencio"],
    ["Gonçalo", "Goncalo", "Goncallo", "Gonçalo"],
    ["Caetano", "Cayetano", "Gaetano"],
    ["Custódio", "Custodio", "Custodia"],
    ["Joaquim", "Joachym", "Joaquym", "Joachin"],
    ["Lourenço", "Lourenco", "Lorenço", "Lorenzo"],
    ["Sebastião", "Sebastiao", "Sebastiam", "Bastião", "Bastiam"],
    ["Gaspar", "Gaspard", "Gasparo"],
    ["Baltasar", "Baltazar", "Balthazar"],
    ["Belchior", "Melchior", "Belquior"],
    ["Bernardo", "Bernardino", "Bernaldo"],
    ["Diogo", "Diego"],
    ["Duarte", "Eduardo"],
    ["Simão", "Simao", "Simam", "Symeão"],
    ["Estêvão", "Estevao", "Estevam", "Estevão", "Estevam"],
    ["Afonso", "Affonso", "Alfonso", "Alphonso"],
    ["Domingos", "Domimgos", "Domingas"],
    ["Félix", "Felix", "Feliz", "Phebe"],
    ["Jerónimo", "Jeronimo", "Geronimo", "Hieronimo", "Ieronimo"],
    ["Martinho", "Martins", "Martin", "Martim"],
    ["Paulo", "Paolo", "Paullo"],
    ["Pedro", "Pero", "Petro"],
    ["Rodrigo", "Rui", "Ruy"],
    ["Vasco", "Basco"],
    ["Xavier", "Javier", "Xabier"],
    ["Bento", "Benedito", "Benneto"],
    ["Álvaro", "Alvaro", "Albaro"],
    ["Brás", "Bras", "Blas"],
    ["Cosme", "Cozme", "Cosmo"],
    ["Dinis", "Diniz", "Diniz"],
    ["Gaspar", "Gaspar"],
    ["Gregório", "Gregorio", "Grygorio"],
    ["Marcos", "Marco", "Marcus"],
    ["Nicolau", "Nicolao", "Nicola"],
    ["Roque", "Rocco", "Roch"],
    ["Salvador", "Salbador"],
    ["Sebastião", "Sebastiao", "Sebastiam"],
    ["Teotónio", "Teotonio", "Theotonio"],
    ["Valentim", "Valentin", "Balentim"],
    # Nomes femininos frequentes
    ["Maria", "Marya", "Marianna"],
    ["Ana", "Anna", "Hanna", "Anica"],
    ["Teresa", "Theresa", "Tereza", "Thereza"],
    ["Isabel", "Izabel", "Ysabel", "Ysavel", "Elisabete", "Elizabeth"],
    ["Brízida", "Brizida", "Brigida", "Brígida", "Brygida"],
    ["Bárbara", "Barbara", "Barbola", "Barba"],
    ["Catarina", "Catharina", "Catherina", "Catalina"],
    ["Guiomar", "Guyomar"],
    ["Helena", "Elena", "Helenna"],
    ["Margarida", "Margarita", "Margaryda"],
    ["Violante", "Yolanda", "Violata"],
    ["Brites", "Brithes"],
    ["Francisca", "Francysca", "Françisca"],
    ["Antónia", "Antonia", "Anttonia"],
    ["Joana", "Joanna", "Jhoana"],
    ["Luísa", "Luisa", "Luiza", "Luysa"],
    ["Rosa", "Roza"],
    ["Rita", "Ritha"],
    ["Clara", "Klara"],
    ["Inês", "Ines", "Inez", "Ynes", "Agnes"],
    ["Madalena", "Magdalena", "Maddalena"],
    ["Esperança", "Esperanca"],
    ["Gracia", "Graça", "Graca"],
    ["Úrsula", "Ursula", "Orsola"],
    ["Vicência", "Vicencia", "Vicensa"],
    ["Paula", "Paola"],
    ["Apolónia", "Apolonia", "Appolonia"],
    ["Benta", "Benedita"],
    ["Doroteia", "Dorothea", "Dorotea"],
    ["Eufémia", "Eufemia", "Euphemia"],
    ["Genoeva", "Genoveva", "Jenovefa"],
    ["Luzia", "Lucia", "Luçia"],
    ["Micaela", "Michaela", "Miquela"],
    ["Quitéria", "Quiteria"],
    ["Senhorinha", "Senhorina"],
    ["Vitória", "Vitoria", "Victoria"],
    # Apelidos / Sobrenomes patronímicos e toponímicos
    ["Vaz", "Vaas", "Vas"],
    ["Pires", "Peres", "Pirez"],
    ["Rodrigues", "Rodriguez"],
    ["Fernandes", "Fernandez", "Hernandes"],
    ["Henriques", "Henriquez", "Anriques"],
    ["Gonçalves", "Goncalves", "Gonçalvez"],
    ["Lopes", "Lopez"],
    ["Nunes", "Nunez"],
    ["Alves", "Alvez", "Alvares", "Álvares"],
    ["Dias", "Diaz"],
    ["Marques", "Marquez"],
    ["Soares", "Suarez"],
    ["Esteves", "Estevens", "Estevez"],
    ["Gomes", "Gomez"],
    ["Mendes", "Mendez"],
    ["Pires", "Perez"],
    ["Sanches", "Sanchez"],
    ["Simões", "Simoes", "Simoens"],
    ["Vieira", "Veyra", "Vyeyra"],
    ["Pinto", "Pincto"],
    ["Borges", "Borghes"],
    ["Coelho", "Coello"],
    ["Cordeiro", "Cordeyro"],
    ["Ferreira", "Ferreyra"],
    ["Figueiredo", "Figueyredo"],
    ["Fonseca", "Fonceca"],
    ["Gouveia", "Gouveya"],
    ["Machado", "Machada"],
    ["Madeira", "Madeyra"],
    ["Monteiro", "Monteyro"],
    ["Moreira", "Moreyra"],
    ["Nogueira", "Nogueyra"],
    ["Oliveira", "Oliveyra"],
    ["Pereira", "Pereyra"],
    ["Pinheiro", "Pinheyro"],
    ["Ribeiro", "Ribeyro"],
    ["Saraiva", "Sarayva"],
    ["Silva", "Sylva"],
    ["Sousa", "Souza"],
    ["Tavares", "Tabarez", "Tabares"],
    ["Teixeira", "Teyxeyra", "Texeyra"],
]

# Mapa normalizado: chave normalizada -> lista ordenada de variantes
_VARIANT_LOOKUP: Dict[str, List[str]] = {}

for cluster in HISTORICAL_CLUSTERS:
    for variant in cluster:
        norm = normalize_token(variant)
        if norm:
            if norm not in _VARIANT_LOOKUP:
                _VARIANT_LOOKUP[norm] = []
            for item in cluster:
                if item not in _VARIANT_LOOKUP[norm]:
                    _VARIANT_LOOKUP[norm].append(item)


def get_token_variants(token: str) -> List[str]:
    """
    Devolve a lista de variantes históricas para uma dada palavra/nome.
    Se não houver registo no mapa, devolve uma lista com o próprio token.
    """
    token_str = token.strip()
    if not token_str:
        return []
    norm = normalize_token(token_str)
    if norm in _VARIANT_LOOKUP:
        variants = list(_VARIANT_LOOKUP[norm])
        # Colocar o token de entrada no início se já existir ou acrescentar
        if token_str in variants:
            variants.remove(token_str)
            variants.insert(0, token_str)
        else:
            variants.insert(0, token_str)
        return variants
    return [token_str]


def expand_name_variants(query: str, max_combinations: int = 32) -> List[str]:
    """
    Expande uma consulta composta por múltiplos nomes para todas as combinações de variantes.
    Ex: "Joao Silva" -> ["Joao Silva", "João Silva", "Joam Silva", "Joan Silva", ...]
    """
    tokens = [t.strip() for t in query.split() if t.strip()]
    if not tokens:
        return []
    if len(tokens) == 1:
        return get_token_variants(tokens[0])

    token_variants = [get_token_variants(t) for t in tokens]
    # Produto cartesiano controlado
    combinations = [[]]
    for variants in token_variants:
        new_comb = []
        for c in combinations:
            for v in variants:
                new_comb.append(c + [v])
        combinations = new_comb

    results = [" ".join(comb) for comb in combinations]
    # Deduplicar preservando ordem
    seen = set()
    deduped = []
    for r in results:
        if r.lower() not in seen:
            seen.add(r.lower())
            deduped.append(r)
        if len(deduped) >= max_combinations:
            break
    return deduped


def soundex_pt(word: str) -> str:
    """
    Algoritmo Soundex adaptado para a fonética da Língua Portuguesa e grafias históricas.
    Gera um código de 4 caracteres (1 letra + 3 dígitos), ex: 'J500', 'T620'.
    
    Regras fonéticas portuguesas aplicadas:
    - Normalização de acentos e diacríticos
    - PH -> F, TH -> T, Y -> I, W -> V
    - CH, X, Ç, S, Z -> 2
    - K, Q, C (duro) -> 2
    - LH -> 4, NH -> 5
    - Consoantes mudas (P em baptismo, C em acto) simplificadas
    - Vogais e H ignorados no corpo do código
    """
    if not word:
        return "0000"

    # 1. Limpeza básica
    cleaned = remove_accents(word).upper()
    cleaned = re.sub(r"[^A-Z]", "", cleaned)
    if not cleaned:
        return "0000"

    # 2. Transformações fonéticas preliminares (substituições arcaicas/fonéticas)
    text = cleaned
    text = text.replace("PH", "F")
    text = text.replace("TH", "T")
    text = text.replace("RH", "R")
    text = text.replace("Y", "I")
    text = text.replace("W", "V")
    text = text.replace("LH", "L")
    text = text.replace("NH", "N")
    text = text.replace("CH", "X")
    text = text.replace("Ç", "S")
    text = text.replace("SC", "S")
    text = text.replace("XC", "S")

    # Primeira letra mantida
    first_letter = text[0]
    tail = text[1:]

    # Tabela de mapeamento fonético para português:
    # 1: B, F, P, V
    # 2: C, G, J, K, Q, S, X, Z
    # 3: D, T
    # 4: L
    # 5: M, N
    # 6: R
    char_map = {
        "B": "1", "F": "1", "P": "1", "V": "1",
        "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
        "D": "3", "T": "3",
        "L": "4",
        "M": "5", "N": "5",
        "R": "6",
    }

    # 3. Codificar cauda
    digits = []
    last_digit = char_map.get(first_letter, "0")

    for ch in tail:
        code = char_map.get(ch, "0")
        if code != "0":
            if code != last_digit:
                digits.append(code)
            last_digit = code
        else:
            # Vogais e H quebram repetições
            last_digit = "0"

    code_str = first_letter + "".join(digits)
    # Preencher com zeros ou truncar a 4 caracteres
    return (code_str + "0000")[:4]


def phonetic_match(word1: str, word2: str) -> bool:
    """Verifica se duas palavras têm o mesmo código Soundex português."""
    return soundex_pt(word1) == soundex_pt(word2)


def build_postgrest_query_condition(query: str, max_variants: int = 8) -> str:
    """
    Constrói a cláusula PostgREST or(...) expandindo variantes históricas.
    Suporta pesquisas com múltiplos termos e apelidos.
    """
    clean_query = query.strip()
    if not clean_query:
        return ""

    tokens = [t for t in clean_query.split() if t]
    variants = expand_name_variants(clean_query, max_combinations=max_variants)

    conditions = []
    for v in variants:
        # Busca em nome, sobrenome e freguesia
        conditions.append(f"nome.ilike.*{v}*")
        conditions.append(f"sobrenome.ilike.*{v}*")

    # Também incluir a busca geral na freguesia para o termo original
    conditions.append(f"freguesia.ilike.*{clean_query}*")

    # Se for uma pesquisa de palavra única, também expandir variantes de token
    if len(tokens) == 1:
        token_vars = get_token_variants(tokens[0])
        for tv in token_vars:
            conditions.append(f"nome.ilike.*{tv}*")
            conditions.append(f"sobrenome.ilike.*{tv}*")

    # Deduplicar preservando ordem
    seen = set()
    deduped = []
    for c in conditions:
        if c not in seen:
            seen.add(c)
            deduped.append(c)

    return f"or({','.join(deduped)})"
