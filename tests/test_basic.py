# tests/test_basic.py
import pytest
from src.db import DatabaseManager
from pathlib import Path
import tempfile

@pytest.fixture
def temp_db():
    """Database temporaneo per test"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    
    db = DatabaseManager(db_path)
    yield db
    
    db_path.unlink()

def test_create_proprieta(temp_db):
    """Test creazione proprietà"""
    data = {
        'nome': 'Test Appartamento',
        'indirizzo': 'Via Test 1',
        'mq_effettivi': 50.0,
        'mq_commerciali': 55.0,
        'valore_mq': 2000.0
    }
    
    prop_id = temp_db.create_proprieta(data)
    assert prop_id > 0
    
    prop = temp_db.get_proprieta_by_id(prop_id)
    assert prop['nome'] == 'Test Appartamento'
    assert prop['mq_effettivi'] == 50.0

def test_update_proprieta(temp_db):
    """Test aggiornamento proprietà"""
    # Crea
    prop_id = temp_db.create_proprieta({
        'nome': 'Original',
        'indirizzo': 'Via Test',
        'mq_effettivi': 50,
        'mq_commerciali': 55,
        'valore_mq': 2000
    })
    
    # Aggiorna
    temp_db.update_proprieta(prop_id, {'nome': 'Updated'})
    
    prop = temp_db.get_proprieta_by_id(prop_id)
    assert prop['nome'] == 'Updated'

def test_delete_proprieta(temp_db):
    """Test eliminazione proprietà"""
    prop_id = temp_db.create_proprieta({
        'nome': 'To Delete',
        'indirizzo': 'Via Test',
        'mq_effettivi': 50,
        'mq_commerciali': 55,
        'valore_mq': 2000
    })
    
    assert temp_db.delete_proprieta(prop_id) is True
    assert temp_db.get_proprieta_by_id(prop_id) is None

def test_filter_non_pagati(temp_db):
    """Test filtro mensilità non pagate"""
    # Crea 2 proprietà: 1 pagata, 1 no
    temp_db.create_proprieta({
        'nome': 'Pagato',
        'indirizzo': 'Via Test 1',
        'mq_effettivi': 50,
        'mq_commerciali': 55,
        'valore_mq': 2000,
        'affittato_a': 'Tizio',
        'affitto_mensile': 1000,
        'mensilita_pagata': 1
    })
    
    temp_db.create_proprieta({
        'nome': 'Non Pagato',
        'indirizzo': 'Via Test 2',
        'mq_effettivi': 60,
        'mq_commerciali': 65,
        'valore_mq': 2000,
        'affittato_a': 'Caio',
        'affitto_mensile': 1200,
        'mensilita_pagata': 0
    })
    
    non_pagati = temp_db.get_all_proprieta({'non_pagati': True})
    assert len(non_pagati) == 1
    assert non_pagati[0]['nome'] == 'Non Pagato'

# Esegui test
if __name__ == "__main__":
    pytest.main([__file__, "-v"])