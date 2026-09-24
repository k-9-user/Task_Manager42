import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from 'react-i18next';
import { googleOAuthUrl, login } from '../services/authService';
import { isValidIdentifier } from '../utils/validation';
import LanguageSwitcher from '../components/LanguageSwitcher';

const FIELD_INPUT = "w-full rounded-lg border border-brand-surface-border bg-brand-surface-alt px-3 py-2.5 text-[15px] text-[#2c1a4d] transition-shadow focus:border-brand-primary focus:outline-none focus:ring-4 focus:ring-brand-primary-soft";

function Login()
{
	const [identifier, setIdentifier] = useState("");
	const [password, setPassword] = useState("");
	const { t } = useTranslation();
	const navigate = useNavigate();
	const [error, setError] = useState("");
	const [searchParams] = useSearchParams();
	const oauthStatus = searchParams.get("oauth");
	const oauthError = oauthStatus === "cancelled"
		? t("login.oauthCancelled")
		: oauthStatus === "failed" ? t("login.oauthFailed") : "";

	async function handleSubmit(e) {
		e.preventDefault();
		setError("");
		const trimmedIdentifier = identifier.trim();
		if (!trimmedIdentifier)
		{
			setError(t("login.identifierRequired"));
			return ;
		}
		if (!password)
		{
			setError(t("login.passwordRequired"));
			return ;
		}
		if (!isValidIdentifier(trimmedIdentifier))
		{
			setError(t("login.invalidIdentifier"));
			return ;
		}

		try
		{
			await login(trimmedIdentifier, password);
			navigate("/projects");
		}
		catch (err)
		{
			setError(err.message);
		}
	}
	return (
		<div className="relative flex min-h-screen flex-col items-center justify-center bg-[image:var(--page-gradient)] p-6 font-sans">
			<div className="absolute right-6 top-5">
				<LanguageSwitcher />
			</div>
			<div className="w-full max-w-[400px] overflow-hidden rounded-2xl bg-brand-surface shadow-[0_20px_45px_rgba(46,16,101,0.45)]">
				<div className="flex flex-col items-center gap-1.5 bg-gradient-to-br from-brand-primary-darker to-brand-primary-dark px-8 pb-5 pt-9 text-center">
					<span className="text-4xl leading-none">📋</span>
					<h1 className="m-0 mt-1.5 text-xl font-semibold tracking-wide text-white">Task Manager</h1>
					<p className="m-0 text-sm text-brand-primary-light">{t("login.subtitle")}</p>
				</div>
				<form className="flex flex-col gap-5 bg-brand-surface p-8" onSubmit={handleSubmit}>
					{(error || oauthError) && (
						<p className="m-0 rounded-lg bg-red-100 px-3 py-2 text-sm text-red-700">{error || oauthError}</p>
					)}
					<div className="flex flex-col gap-4">
						<div className="flex flex-col gap-1.5">
							<label htmlFor='identifier' className="text-[13px] font-semibold text-brand-primary-dark">{t("login.identifier")}</label>
							<input id='identifier' type="text" autoComplete="username" value={identifier} onChange={(e) => setIdentifier(e.target.value)} className={FIELD_INPUT} />
						</div>
						<div className="flex flex-col gap-1.5">
							<label htmlFor='password' className="text-[13px] font-semibold text-brand-primary-dark">{t("login.password")}</label>
							<input id='password' type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} className={FIELD_INPUT} />
						</div>
					</div>
					<button
						type="submit"
						className="w-full cursor-pointer rounded-lg border-none bg-brand-primary px-4 py-3 text-[15px] font-bold text-white transition-colors hover:bg-brand-primary-hover active:translate-y-px"
					>
						{t("login.submit")}
					</button>
					<div className="flex items-center gap-3 text-[11px] uppercase text-brand-primary-light before:h-px before:flex-1 before:bg-brand-surface-border after:h-px after:flex-1 after:bg-brand-surface-border">
						<span>{t("login.or")}</span>
					</div>
					<a
						href={googleOAuthUrl}
						className="w-full rounded-lg border border-brand-surface-border bg-brand-surface-alt px-4 py-2.5 text-center text-sm font-semibold text-brand-primary-dark no-underline transition-colors hover:bg-brand-primary hover:text-white hover:border-brand-primary"
					>
						{t("login.google")}
					</a>
					<p className="m-0 text-center text-sm text-[#6b21a8]">
						{t("login.noAccount")} <Link to="/register" className="font-bold text-brand-primary no-underline hover:underline">{t("login.register")}</Link>
					</p>
				</form>
			</div>
		</div>
	);
}

export default Login;
