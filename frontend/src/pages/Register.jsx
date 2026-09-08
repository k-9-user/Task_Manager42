import { useState } from 'react';
import './register.css';
import { Link } from "react-router-dom";
import { isvalidemail } from '../utils/validation';
import { useTranslation } from 'react-i18next';
import LanguageSwitcher from '../components/LanguageSwitcher';

function Register()
{
	const [username, setUsername] = useState("");
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [confirmPassword, setConfirmPassword] = useState("");
	const [error, setError] = useState("");
	const { t } = useTranslation();

	function handleSubmit (e) {
		e.preventDefault();
		if (!username.trim() || !email.trim() || !password || !confirmPassword)
		{
			if (!username.trim())
				setError(t("register.username"));
			else if (!email.trim())
				setError(t("register.email"));
			else if (!password)
				setError(t("register.password"));
			else
				setError(t("register.cpassword"));
			return ;
		}
		if (!isvalidemail(email))
		{
			setError(t("register.invaemail"));
			return ;
		}
		if (password !== confirmPassword)
		{
			setError(t("register.falsepassword"));
			return ;
		}
		setError("");
		console.log(`Nouveau compte : ${username}, ${email}`);
	}
	return (
		<div className='register-page'>
			<h1>Transcendance</h1>
			<div className='register-window'>
				<div className='register-titlebar'>{t("login.register")}</div>
				<form className='register-box' onSubmit={handleSubmit}>
					{error && <p className='error'>{error}</p>}
					<div className='input-group'>
						<div className='input-field'>
							<label htmlFor='username'>{t("login.username")} : </label>
							<input id='username' type="text" required value={username} onChange={(e) => setUsername(e.target.value)} />
						</div>
						<div className='input-field'>
							<label htmlFor='email'>Email : </label>
							<input id='email' type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
						</div>
						<div className='input-field'>
							<label htmlFor='password'>{t("login.password")} : </label>
							<input id='password' type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
						</div>
						<div className='input-field'>
							<label htmlFor='confirmpassword'>{t("register.confirmpassword")} : </label>
							<input id='confirmpassword' type="password" required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
						</div>
						<button>{t("register.createcount")}</button>
						<div className='login-link'>
							<Link className='btn-link' to="/login">{t("register.return")}</Link>
						</div>
					</div>
				</form>
			</div>
		</div>
	);
}

export default Register;