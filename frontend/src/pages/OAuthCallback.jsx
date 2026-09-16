import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { exchangeGoogleOAuth } from "../services/authService";
import "./login.css";


function OAuthCallback() {
	const started = useRef(false);
	const navigate = useNavigate();
	const { t } = useTranslation();

	useEffect(() => {
		if (started.current)
			return;
		started.current = true;
		exchangeGoogleOAuth()
			.then(({ token }) => {
				localStorage.setItem("token", token);
				navigate("/projects", { replace: true });
			})
			.catch(() => navigate("/login?oauth=failed", { replace: true }));
	}, [navigate]);

	return (
		<div className="login-page oauth-callback" aria-live="polite">
			<div className="login-window">
				<div className="login-titlebar">{t("login.google")}</div>
				<div className="login-box">{t("login.oauthLoading")}</div>
			</div>
		</div>
	);
}

export default OAuthCallback;
