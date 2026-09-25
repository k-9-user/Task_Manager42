import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { exchangeGoogleOAuth } from "../services/authService";


function OAuthCallback() {
	const started = useRef(false);
	const navigate = useNavigate();
	const { t } = useTranslation();

	useEffect(() => {
		if (started.current)
			return;
		started.current = true;
		exchangeGoogleOAuth()
			.then(() => navigate("/projects", { replace: true }))
			.catch(() => navigate("/login?oauth=failed", { replace: true }));
	}, [navigate]);

	return (
		<div className="flex min-h-screen flex-col items-center justify-center bg-[image:var(--page-gradient)] p-6 font-sans" aria-live="polite">
			<div className="w-full max-w-[400px] overflow-hidden rounded-2xl bg-brand-surface shadow-[0_20px_45px_rgba(46,16,101,0.45)]">
				<div className="flex flex-col items-center gap-1.5 bg-gradient-to-br from-brand-primary-darker to-brand-primary-dark px-8 py-6 text-center">
					<h1 className="m-0 text-xl font-semibold tracking-wide text-white">{t("login.google")}</h1>
				</div>
				<div className="bg-brand-surface p-8 text-center text-sm text-brand-primary-dark">{t("login.oauthLoading")}</div>
			</div>
		</div>
	);
}

export default OAuthCallback;
