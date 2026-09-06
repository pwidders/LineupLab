import streamlit as st
from supabase import create_client


AUTH_ACCESS_TOKEN_KEY = "nfl_auth_access_token"
AUTH_REFRESH_TOKEN_KEY = "nfl_auth_refresh_token"
AUTH_USER_ID_KEY = "nfl_auth_user_id"
AUTH_EMAIL_KEY = "nfl_auth_email"


def _get_public_supabase_key():
    for key_name in [
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_ANON_KEY",
    ]:
        try:
            value = st.secrets[key_name]
        except Exception:
            value = None

        if value:
            return value

    raise KeyError(
        "Add SUPABASE_PUBLISHABLE_KEY or SUPABASE_ANON_KEY "
        "to Streamlit secrets."
    )


def get_authenticated_client():
    client = create_client(
        st.secrets["SUPABASE_URL"],
        _get_public_supabase_key(),
    )

    access_token = st.session_state.get(
        AUTH_ACCESS_TOKEN_KEY
    )
    refresh_token = st.session_state.get(
        AUTH_REFRESH_TOKEN_KEY
    )

    if access_token and refresh_token:
        session_response = client.auth.set_session(
            access_token,
            refresh_token,
        )

        session = getattr(
            session_response,
            "session",
            None,
        )

        if session is not None:
            st.session_state[
                AUTH_ACCESS_TOKEN_KEY
            ] = session.access_token
            st.session_state[
                AUTH_REFRESH_TOKEN_KEY
            ] = session.refresh_token

            user = getattr(
                session,
                "user",
                None,
            )

            if user is not None:
                st.session_state[
                    AUTH_USER_ID_KEY
                ] = str(user.id)
                st.session_state[
                    AUTH_EMAIL_KEY
                ] = str(user.email or "")

    return client


def _save_auth_response(response):
    session = getattr(response, "session", None)
    user = getattr(response, "user", None)

    if session is not None:
        st.session_state[
            AUTH_ACCESS_TOKEN_KEY
        ] = session.access_token
        st.session_state[
            AUTH_REFRESH_TOKEN_KEY
        ] = session.refresh_token

    if user is None and session is not None:
        user = getattr(session, "user", None)

    if user is not None:
        st.session_state[
            AUTH_USER_ID_KEY
        ] = str(user.id)
        st.session_state[
            AUTH_EMAIL_KEY
        ] = str(user.email or "")


def clear_auth_session():
    for key in [
        AUTH_ACCESS_TOKEN_KEY,
        AUTH_REFRESH_TOKEN_KEY,
        AUTH_USER_ID_KEY,
        AUTH_EMAIL_KEY,
    ]:
        st.session_state.pop(key, None)


def get_current_user_id():
    user_id = st.session_state.get(
        AUTH_USER_ID_KEY
    )

    if not user_id:
        raise PermissionError(
            "You must be signed in to access NFL user data."
        )

    return str(user_id)


def render_auth_gate():
    if st.session_state.get(AUTH_ACCESS_TOKEN_KEY):
        try:
            client = get_authenticated_client()
            response = client.auth.get_user()
            user = getattr(response, "user", None)

            if user is not None:
                st.session_state[
                    AUTH_USER_ID_KEY
                ] = str(user.id)
                st.session_state[
                    AUTH_EMAIL_KEY
                ] = str(user.email or "")
                return True

        except Exception:
            clear_auth_session()

    st.markdown("### 🔐 Sign in to LineupLab")
    st.caption(
        "Your Final Lineups and future Performance Center history "
        "will stay separate from other LineupLab users."
    )

    sign_in_tab, create_tab = st.tabs(
        ["Sign In", "Create Account"]
    )

    with sign_in_tab:
        with st.form("nfl_sign_in_form"):
            email = st.text_input(
                "Email",
                key="nfl_sign_in_email",
            )
            password = st.text_input(
                "Password",
                type="password",
                key="nfl_sign_in_password",
            )
            submitted = st.form_submit_button(
                "Sign In",
                type="primary",
            )

        if submitted:
            try:
                client = create_client(
                    st.secrets["SUPABASE_URL"],
                    _get_public_supabase_key(),
                )

                response = (
                    client.auth.sign_in_with_password(
                        {
                            "email": email.strip(),
                            "password": password,
                        }
                    )
                )

                _save_auth_response(response)
                st.rerun()

            except Exception as exc:
                st.error(f"Could not sign in: {exc}")

    with create_tab:
        with st.form("nfl_create_account_form"):
            new_email = st.text_input(
                "Email",
                key="nfl_signup_email",
            )
            new_password = st.text_input(
                "Password",
                type="password",
                key="nfl_signup_password",
                help="Use at least 6 characters.",
            )
            confirm_password = st.text_input(
                "Confirm Password",
                type="password",
                key="nfl_signup_confirm_password",
            )
            create_submitted = (
                st.form_submit_button(
                    "Create Account",
                    type="primary",
                )
            )

        if create_submitted:
            if len(new_password) < 6:
                st.error(
                    "Password must be at least 6 characters."
                )
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                try:
                    client = create_client(
                        st.secrets["SUPABASE_URL"],
                        _get_public_supabase_key(),
                    )

                    response = client.auth.sign_up(
                        {
                            "email": new_email.strip(),
                            "password": new_password,
                        }
                    )

                    _save_auth_response(response)

                    if getattr(
                        response,
                        "session",
                        None,
                    ) is not None:
                        st.rerun()
                    else:
                        st.success(
                            "Account created. Check your email "
                            "for the Supabase confirmation link, "
                            "then return here and sign in."
                        )

                except Exception as exc:
                    st.error(
                        f"Could not create account: {exc}"
                    )

    return False


def render_account_controls():
    email = st.session_state.get(
        AUTH_EMAIL_KEY,
        "",
    )

    with st.sidebar:
        st.markdown("### LineupLab Account")

        if email:
            st.caption(f"Signed in as **{email}**")

        if st.button(
            "Sign Out",
            key="nfl_sign_out",
            use_container_width=True,
        ):
            try:
                client = get_authenticated_client()
                client.auth.sign_out()
            except Exception:
                pass

            clear_auth_session()
            st.rerun()
