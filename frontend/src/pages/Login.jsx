import { useState } from 'react'
import "@fontsource/nabla";
import './login.css';
import { Link } from "react-router-dom";
import { useTranslation } from 'react-i18next';
import LanguageSwitcher from '../components/LanguageSwitcher';

function Login()
{
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const { t } = useTranslation();

	function handleSubmit(e) {
		e.preventDefault();
		console.log(`Utilisateur : ${email}`);
		console.log(`Mot de passe : ${password}`);
		// TODO: appel à authService.login(email, password)
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
						<div className='input-field'>
							<label htmlFor='username'>{t("login.username")} : </label>
							<input id='username' type="text" value={email} onChange={(e) => setEmail(e.target.value)}
							/>
						</div>
						<div className='input-field'>
							<label htmlFor='password'>{t("login.password")} : </label>
							<input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
							/>
						</div>
						<div className='login-action'>
							<button>{t("login.submit")}</button>
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