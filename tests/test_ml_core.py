import pandas as pd

from app.ml_core import clean_genres, make_match_key, prepare_catalogue


def test_make_match_key_basic():
    assert make_match_key("Inception", 2010) == "inception_2010"


def test_make_match_key_removes_punctuation_and_special_chars():
    assert make_match_key("WALL·E", 2008) == "walle_2008"
    assert make_match_key("Howl's Moving Castle", 2004) == "howls moving castle_2004"
    assert make_match_key("Monsters, Inc.", 2001) == "monsters inc_2001"


def test_make_match_key_handles_missing_year():
    assert make_match_key("Some Movie", None) == "some movie_unknown"
    assert make_match_key("Some Movie", float("nan")) == "some movie_unknown"


def test_make_match_key_strips_and_lowercases():
    assert make_match_key("  The Matrix  ", 1999) == "the matrix_1999"


def test_clean_genres_parses_string_list():
    assert clean_genres("['Action', 'Drama']") == ["Action", "Drama"]


def test_clean_genres_handles_already_a_list():
    assert clean_genres(["Action", "Drama"]) == ["Action", "Drama"]


def test_clean_genres_handles_none_and_nan():
    assert clean_genres(None) == []
    assert clean_genres(float("nan")) == []


def test_clean_genres_handles_plain_unformatted_string():
    assert clean_genres("Action") == ["Action"]


def test_prepare_catalogue_filters_and_computes_year():
    df = pd.DataFrame(
        {
            "title": ["Movie A", "Movie B", "Movie C"],
            "status": ["Released", "Post Production", "Released"],
            "release_date": ["2010-07-16", "2025-01-01", "not_a_date"],
        }
    )

    result = prepare_catalogue(df)

    # Movie B exclue (pas sortie), Movie C exclue (date invalide -> year manquant)
    assert list(result["title"]) == ["Movie A"]
    assert result.loc[0, "year"] == 2010
    assert result["year"].dtype == "int64"
