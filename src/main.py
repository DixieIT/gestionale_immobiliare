import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta
from PIL import Image
import shutil

try:
    from . import settings
    from .db import db
    from .excel_io import excel_io
except ImportError:
    import settings
    from db import db
    from excel_io import excel_io


# Configurazione pagina
st.set_page_config(
    page_title="Gestionale Immobiliare",
    page_icon="🏠",
    layout="wide"
)

# Inizializzazione session state
if 'selected_prop_id' not in st.session_state:
    st.session_state.selected_prop_id = None
if 'refresh' not in st.session_state:
    st.session_state.refresh = 0

def calcola_giorni_scadenza(data_fine: str) -> int:
    """Calcola giorni alla scadenza"""
    if not data_fine:
        return 999
    try:
        scadenza = datetime.fromisoformat(data_fine).date()
        return (scadenza - datetime.now().date()).days
    except:
        return 999

def render_sidebar():
    """Sidebar con elenco proprietà e filtri"""
    st.sidebar.title("🏠 Immobili")
    
    # Filtri
    st.sidebar.subheader("🔍 Filtri")
    cerca = st.sidebar.text_input("Cerca per nome", "")
    
    ordina = st.sidebar.selectbox(
        "Ordina per",
        ["nome", "valore_mq DESC", "contratto_fine ASC"]
    )
    
    solo_affitti = st.sidebar.checkbox("Solo affitti attivi")
    scadenza_60 = st.sidebar.checkbox("Scadenza < 60 giorni")
    non_pagati = st.sidebar.checkbox("Mensilità non pagate")
    
    # Applica filtri
    filters = {
        'order_by': ordina,
        'solo_affitti': solo_affitti,
        'scadenza_giorni': 60 if scadenza_60 else None,
        'non_pagati': non_pagati
    }
    
    proprieta = db.get_all_proprieta(filters)
    
    # Filtra per ricerca testuale
    if cerca:
        proprieta = [p for p in proprieta if cerca.lower() in p['nome'].lower()]
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📋 Elenco")
    
    for prop in proprieta:
        giorni_scadenza = calcola_giorni_scadenza(prop['contratto_fine'])
        
        # Badge stato
        if prop['affittato_a']:
            badge = "🟢" if prop['mensilita_pagata'] else "🔴"
            affitto_info = f"{badge} {prop['affitto_mensile']:.0f}€"
        else:
            affitto_info = "⚪ Libero"
        
        warning = f" ⚠️ {giorni_scadenza}gg" if 0 < giorni_scadenza < 60 else ""
        
        if st.sidebar.button(
            f"{prop['nome']}\n{affitto_info}{warning}",
            key=f"prop_{prop['id']}",
            use_container_width=True
        ):
            st.session_state.selected_prop_id = int(prop['id'])
            st.session_state.edit_mode = None
            st.session_state.confirm_delete = None

def render_scheda_immobile(prop_id: int):
    """Render scheda dettagliata immobile"""
    prop = db.get_proprieta_by_id(prop_id)
    
    if not prop:
        st.error("Proprietà non trovata")
        return
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # Immagine
        img_path = settings.IMAGES_DIR / prop['immagine_path'] if prop['immagine_path'] else None
        if img_path and img_path.exists():
            st.image(str(img_path), use_container_width=True)
        else:
            st.info("📷 Nessuna immagine")
    
    with col2:
        st.subheader(prop['nome'])
        st.write(f"**Indirizzo**: {prop['indirizzo']}")
        
        col_mq1, col_mq2, col_val = st.columns(3)
        col_mq1.metric("MQ Effettivi", f"{prop['mq_effettivi']:.1f}")
        col_mq2.metric("MQ Commerciali", f"{prop['mq_commerciali']:.1f}")
        col_val.metric("Valore €/m²", f"{prop['valore_mq']:.0f}€")
        
        valore_totale = prop['mq_commerciali'] * prop['valore_mq']
        st.write(f"**Valore Totale**: {valore_totale:,.0f}€")
    
    st.markdown("---")
    
    # Dati affitto
    if prop['affittato_a']:
        col_aff1, col_aff2 = st.columns(2)
        
        with col_aff1:
            st.write(f"**Affittato a**: {prop['affittato_a']}")
            st.write(f"**Canone mensile**: {prop['affitto_mensile']:,.2f}€")
        
        with col_aff2:
            st.write(f"**Contratto**: {prop['contratto_inizio']} → {prop['contratto_fine']}")
            
            giorni = calcola_giorni_scadenza(prop['contratto_fine'])
            if giorni < 0:
                st.error(f"⏰ SCADUTO da {abs(giorni)} giorni")
            elif giorni < 60:
                st.warning(f"⚠️ Scade tra {giorni} giorni")
            else:
                st.success(f"✅ Scade tra {giorni} giorni")
            
            if prop['mensilita_pagata']:
                st.success("🟢 **Mensilità PAGATA**")
            else:
                st.error("🔴 **Mensilità NON PAGATA**")
    else:
        st.info("⚪ Immobile attualmente libero")
    
    st.markdown("---")
    
    # Azioni
    col_edit, col_del, col_pdf = st.columns([1, 1, 2])
    
    with col_edit:
        if st.button("✏️ Modifica", use_container_width=True):
            st.session_state.edit_mode = prop_id
            st.rerun()
    
    with col_del:
        if st.button("🗑️ Elimina", use_container_width=True, type="secondary"):
            if st.session_state.get('confirm_delete') == prop_id:
                db.delete_proprieta(prop_id)
                st.session_state.selected_prop_id = None
                st.session_state.confirm_delete = None
                st.success("✅ Eliminato!")
                st.rerun()
            else:
                st.session_state.confirm_delete = prop_id
                st.warning("⚠️ Clicca di nuovo per confermare")

def render_form_proprieta(prop_id: int = None):
    """Form CRUD proprietà"""
    prop = db.get_proprieta_by_id(prop_id) if prop_id else {}
    
    with st.form("form_proprieta"):
        st.subheader("➕ Nuova Proprietà" if not prop_id else "✏️ Modifica Proprietà")
        
        col1, col2 = st.columns(2)
        
        with col1:
            nome = st.text_input("Nome *", value=prop.get('nome', ''))
            indirizzo = st.text_area("Indirizzo *", value=prop.get('indirizzo', ''))
            mq_eff = st.number_input("MQ Effettivi *", min_value=1.0, value=float(prop.get('mq_effettivi', 50)))
            mq_comm = st.number_input("MQ Commerciali *", min_value=1.0, value=float(prop.get('mq_commerciali', 60)))
            valore_mq = st.number_input("Valore €/m² *", min_value=1.0, value=float(prop.get('valore_mq', 2000)))
        
        with col2:
            affittato_a = st.text_input("Affittato a", value=prop.get('affittato_a', '') or '')
            affitto_mensile = st.number_input("Canone Mensile €", min_value=0.0, value=float(prop.get('affitto_mensile', 0)))
            
            contratto_inizio = st.date_input(
                "Contratto Inizio",
                value=datetime.fromisoformat(prop['contratto_inizio']).date() if prop.get('contratto_inizio') else None
            )
            contratto_fine = st.date_input(
                "Contratto Fine",
                value=datetime.fromisoformat(prop['contratto_fine']).date() if prop.get('contratto_fine') else None
            )
            
            mensilita_pagata = st.checkbox("Mensilità Pagata", value=bool(prop.get('mensilita_pagata', 0)))
            
            immagine = st.file_uploader(
                "Carica Foto",
                type=['jpg', 'jpeg', 'png', 'webp'],
                help=f"Max {settings.MAX_IMAGE_SIZE_MB}MB"
            )
        
        submitted = st.form_submit_button("💾 Salva", type="primary", use_container_width=True)
        
        if submitted:
            # Validazioni
            if not nome or not indirizzo:
                st.error("❌ Nome e indirizzo sono obbligatori")
                return
            
            if mq_comm < mq_eff:
                st.error("❌ MQ Commerciali devono essere >= MQ Effettivi")
                return
            
            # Gestione immagine
            immagine_path = prop.get('immagine_path')
            if immagine:
                # Salva nuova immagine
                ext = Path(immagine.name).suffix
                filename = f"{nome.lower().replace(' ', '_')}_{datetime.now().timestamp()}{ext}"
                img_path = settings.IMAGES_DIR / filename
                
                with open(img_path, 'wb') as f:
                    f.write(immagine.getbuffer())
                
                immagine_path = filename
            
            # Prepara dati
            data = {
                'nome': nome,
                'indirizzo': indirizzo,
                'mq_effettivi': mq_eff,
                'mq_commerciali': mq_comm,
                'valore_mq': valore_mq,
                'affittato_a': affittato_a if affittato_a else None,
                'affitto_mensile': affitto_mensile,
                'contratto_inizio': contratto_inizio.isoformat() if contratto_inizio else None,
                'contratto_fine': contratto_fine.isoformat() if contratto_fine else None,
                'mensilita_pagata': 1 if mensilita_pagata else 0,
                'immagine_path': immagine_path
            }
            
            try:
                if prop_id:
                    db.update_proprieta(prop_id, data)
                    st.success("✅ Proprietà aggiornata!")
                    st.session_state.edit_mode = None
                else:
                    new_id = db.create_proprieta(data)
                    st.success(f"✅ Proprietà creata! (ID: {new_id})")
                    st.session_state.selected_prop_id = new_id
                
                st.rerun()
            except Exception as e:
                st.error(f"❌ Errore: {str(e)}")

def render_azioni_globali():
    """Azioni Import/Export/Sync"""
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 Azioni Globali")
    
    # Nuovo immobile
    if st.sidebar.button("➕ Nuovo Immobile", use_container_width=True, type="primary"):
        st.session_state.edit_mode = 0
        st.session_state.selected_prop_id = None
        st.rerun()
    
    # Export Excel
    if st.sidebar.button("📤 Export Excel", use_container_width=True):
        try:
            export_path = settings.DATA_DIR / f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            excel_io.export_to_excel(export_path)
            
            with open(export_path, 'rb') as f:
                st.sidebar.download_button(
                    "⬇️ Scarica File",
                    f.read(),
                    file_name=export_path.name,
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
            st.sidebar.success("✅ Export completato!")
        except Exception as e:
            st.sidebar.error(f"❌ Errore export: {e}")
    
    # Import Excel
    uploaded_file = st.sidebar.file_uploader("📥 Import Excel", type=['xlsx'])
    if uploaded_file:
        try:
            temp_path = settings.DATA_DIR / "temp_import.xlsx"
            with open(temp_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            
            count, errors = excel_io.import_from_excel(temp_path)
            
            if errors:
                st.sidebar.warning(f"⚠️ Importati {count}, {len(errors)} errori:")
                for err in errors[:5]:  # Mostra max 5 errori
                    st.sidebar.text(err)
            else:
                st.sidebar.success(f"✅ Importati {count} immobili!")
            
            temp_path.unlink()
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"❌ Errore import: {e}")
    
    # Toggle Sync API
    st.sidebar.markdown("---")
    sync_enabled = st.sidebar.toggle(
        "🔄 Sync API",
        value=settings.SYNC_MODE == "api",
        help="Sincronizza con server remoto"
    )
    
    if sync_enabled and settings.SYNC_MODE == "local":
        settings.SYNC_MODE = "api"
        st.sidebar.info(f"🌐 Connesso a: {settings.API_BASE_URL}")
    elif not sync_enabled and settings.SYNC_MODE == "api":
        settings.SYNC_MODE = "local"
        st.sidebar.info("💾 Modalità locale")

def main():
    """Main app logic"""
    st.title("🏠 Gestionale Immobiliare")
    
    # Render sidebar
    render_sidebar()
    render_azioni_globali()
    
    # Main content
    if st.session_state.get('edit_mode') is not None:
        # Mostra form
        render_form_proprieta(st.session_state.edit_mode if st.session_state.edit_mode > 0 else None)
        
        if st.button("❌ Annulla"):
            st.session_state.edit_mode = None
            st.rerun()
    
    elif st.session_state.get('selected_prop_id') is not None:
        # Mostra scheda immobile
        render_scheda_immobile(int(st.session_state.selected_prop_id))
    
    if 'edit_mode' not in st.session_state:
        st.session_state.edit_mode = None
    else:
        # Home / Dashboard
        st.info("👈 Seleziona un immobile dalla barra laterale o crea uno nuovo")
        
        # Statistiche rapide
        proprieta = db.get_all_proprieta()
        
        if proprieta:
            col1, col2, col3, col4 = st.columns(4)
            
            affitti_attivi = [p for p in proprieta if p['affittato_a']]
            non_pagati = [p for p in affitti_attivi if not p['mensilita_pagata']]
            scadenze_vicine = [p for p in proprieta if calcola_giorni_scadenza(p['contratto_fine']) < 60]
            
            col1.metric("📋 Totale Immobili", len(proprieta))
            col2.metric("🏠 Affitti Attivi", len(affitti_attivi))
            col3.metric("🔴 Mensilità Non Pagate", len(non_pagati))
            col4.metric("⚠️ Scadenze < 60gg", len(scadenze_vicine))
            
            # Entrate mensili
            entrate_mensili = sum(p['affitto_mensile'] for p in affitti_attivi)
            st.metric("💰 Entrate Mensili Totali", f"{entrate_mensili:,.2f}€")

if __name__ == "__main__":
    main()