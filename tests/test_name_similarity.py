from people_memory.repository import _name_similarity, _surname_similarity


def test_name_similarity_catches_typo_and_reordered_name() -> None:
    assert _name_similarity("Aster Vale", "Aster Vail") >= 0.78
    assert _name_similarity("Aster Vale", "Vale Aster") == 1.0


def test_name_similarity_rejects_unrelated_people() -> None:
    assert _name_similarity("Aster Vale", "Nova Lumen") < 0.78


def test_surname_similarity_ignores_a_shared_first_name() -> None:
    # Le cas mesuré le 22/11 : un prénom partagé suffit à dépasser le seuil de la chaîne entière,
    # alors que les patronymes n'ont rien à voir.
    assert _name_similarity("Camille Morin", "Camille Lemoine") >= 0.78
    assert _surname_similarity("Camille Morin", "Camille Lemoine") < 0.7
    assert _surname_similarity("Florianne C.", "Florian P") < 0.7


def test_surname_similarity_keeps_typos_and_inverted_names() -> None:
    assert _surname_similarity("Aster Vale", "Aster Vail") >= 0.7
    # Ordre inversé : le patronyme de gauche doit retrouver n'importe quel mot de droite.
    assert _surname_similarity("Dominique Forien", "Forien Dominique") == 1.0
