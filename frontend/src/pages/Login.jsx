import { useState } from 'react'
import './login.css';
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from 'react-i18next';
import { googleOAuthUrl, login } from '../services/authService';
import LanguageSwitcher from '../components/LanguageSwitcher';

function Login()
{
	const [email, setEmail] = useState("");
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

		try
		{
			await login(email, password);
			navigate("/projects");
		}
		catch (err)
		{
			setError(err.message);
		}
	}
	return (
		<div className="login-page">
			<div className='page-header'>
				<h1>Transcendance</h1>
				<LanguageSwitcher />
			</div>
			<div className='login-window'>
				<div className='login-titlebar'>Connexion</div>
				<form className="login-box" onSubmit={handleSubmit}>
					<div className="input-group">
						{(error || oauthError) && <p className='error'>{error || oauthError}</p>}
						<div className='input-field'>
							<label htmlFor='username'>{t("login.username")} : </label>
							<input id='username' type="text" value={email} onChange={(e) => setEmail(e.target.value)}
							/>
						</div>
						<div className='input-field'>
							<label htmlFor='password'>{t("login.password")} : </label>
							<input id='password' type="password" value={password} onChange={(e) => setPassword(e.target.value)}
							/>
						</div>
						<div className='login-action'>
							<button>{t("login.submit")}</button>
						</div>
						<div className='oauth-action'>
							<a href={googleOAuthUrl} className='btn-link'>{t("login.google")}</a>
						</div>
						<div className='register-link'>
							<Link to="/register" className='btn-link'>{t("login.register")}</Link>
						</div>
					</div>
				</form>
			</div>
		</div>
	);
}

export default Login;
