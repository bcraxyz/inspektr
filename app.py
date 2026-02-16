import os
import streamlit as st
from google.cloud import dlp_v2

# Streamlit app config
st.set_page_config(page_title="Inspektr", page_icon="🔍", initial_sidebar_state="auto")

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")

if not PROJECT_ID or not LOCATION:
    raise EnvironmentError("Missing GOOGLE_CLOUD_PROJECT or GOOGLE_CLOUD_LOCATION environment variable.")

parent = f"projects/{PROJECT_ID}/locations/{LOCATION}"

if "dlp_client" not in st.session_state:
    st.session_state.dlp_client = dlp_v2.DlpServiceClient()

if "deid_method" not in st.session_state:
    st.session_state.deid_method = "Replace with [infoType]"

# Inspektr settings
with st.sidebar:
    st.title("🔍 Inspektr")
    # Uncomment when making these settings configurable
    # with st.expander("Google Cloud Settings", expanded=False):
    #     project = st.text_input("Project ID", value=PROJECT_ID, disabled=True)
    #     location = st.text_input("Location", value=LOCATION, disabled=True)
    
    with st.expander("Inspection Settings", expanded=True):
        enable_inspection = st.checkbox("Inspect only", value=True, disabled=True)
        enabled_infotypes = [ 
            "PASSPORT",
            "GOVERNMENT_ID",
            "EMAIL_ADDRESS", 
            "PHONE_NUMBER",
            "CREDIT_CARD_DATA",
            "SECURITY_DATA",
            "IP_ADDRESS"
        ]
        col1, col2 = st.columns([0.05, 0.95])
        with col2:
            items_text = "  \n".join([f"✅ {infotype}" for infotype in enabled_infotypes])
            st.caption(items_text)
    
    with st.expander("De-Identification Settings", expanded=True):
        enable_deid = st.checkbox("Inspect and de-identify", value=False)

        if enable_deid:
            col1, col2 = st.columns([0.05, 0.95])
            with col2:
                st.radio(
                    "",
                    options=[
                        "Redact",
                        "Replace with [infoType]",
                        "Replace with *[redacted]*",
                        "Mask with #"
                    ],
                    key="deid_method",
                    label_visibility="collapsed"
                )

# Initialise session state for client and messages
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User-Assistant chat interaction
if input := st.chat_input("Ask anything"):
    if not input:
        st.stop()

    with st.chat_message("user"):
        if input:
            st.markdown(input)
        
        st.session_state.messages.append({"role": "user", "content": input})

    with st.chat_message("assistant"):
        try:
            with st.spinner("Please wait..."):
                dlp = st.session_state.dlp_client

                inspect_config = {
                    "info_types": [{"name": t} for t in enabled_infotypes],
                    "include_quote": True,
                }

                item = {"value": input}

                inspect_response = dlp.inspect_content(
                    request={
                        "parent": parent,
                        "inspect_config": inspect_config,
                        "item": item,
                    }
                )
                findings = inspect_response.result.findings
                
                if enable_deid:

                    if st.session_state.deid_method == "Redact":
                        transformation = {
                            "primitive_transformation": {
                                "redact_config": {}
                            }
                        }

                    elif st.session_state.deid_method == "Replace with [infoType]":
                        transformation = {
                            "primitive_transformation": {
                                "replace_with_info_type_config": {}
                            }
                        }

                    elif st.session_state.deid_method == "Replace with *[redacted]*":
                        transformation = {
                            "primitive_transformation": {
                                "replace_config": {"new_value": {"string_value": "*[redacted]*"}}
                            }
                        }

                    elif st.session_state.deid_method == "Mask with #":
                        transformation = {
                            "primitive_transformation": {
                                "character_mask_config": {
                                    "masking_character": "#"
                                }
                            }
                        }

                    deidentify_config = {
                        "info_type_transformations": {
                            "transformations": [
                                {
                                    "info_types": [{"name": t} for t in enabled_infotypes],
                                    "primitive_transformation": transformation["primitive_transformation"]
                                }
                            ]
                        }
                    }

                    deid_response = dlp.deidentify_content(
                        request={
                            "parent": parent,
                            "inspect_config": inspect_config,
                            "deidentify_config": deidentify_config,
                            "item": {
                                "value": input,
                            },
                        }
                    )
                    output = deid_response.item.value
                    st.info(output)

                else:
                    if findings:
                        items = [f"* {f.info_type.name}: {f.quote}" for f in findings]
                        output = "🚨 Sensitive data found!\n\n" + "\n".join(items)
                        st.warning(output)
                    else:
                        output = "✅ No sensitive data found."
                        st.success(output)

                st.session_state.messages.append({"role": "assistant", "content": output})

        except Exception as e:
            st.error(f"Error: {e}")
