import { useState } from 'react';
import './register.css';
import { Link } from "react-router-dom";
import {
	PASSWORD_MAX_LENGTH,
	PASSWORD_MIN_LENGTH,
	hasControlCharacters,
	isvalidemail,
	isvalidpassword,
	isvalidusername,
	passwordLength,
} from '../utils/validation';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { register } from "../services/authService";
import LanguageSwitcher from '../components/LanguageSwitcher';

function Register()
{
	const [username, setUsername] = useState("");
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [confirmPassword, setConfirmPassword] = useState("");
	const [error, setError] = useState("");
	const { t } = useTranslation();
	const navigate = useNavigate();
	const passwordLimits = { min: PASSWORD_MIN_LENGTH, max: PASSWORD_MAX_LENGTH };

	async function handleSubmit (e) {
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
		if (!isvalidusername(username))
		{
			setError(t("register.invausername"));
			return ;
		}
		if (hasControlCharacters(password))
		{
			setError(t("register.invapasswordchars"));
			return ;
		}
		if (!isvalidpassword(password))
		{
			setError(passwordLength(password) > PASSWORD_MAX_LENGTH
				? t("register.invapasswordlong", passwordLimits)
				: t("register.invapassword", passwordLimits));
			return ;
		}
		if (password !== confirmPassword)
		{
			setError(t("register.falsepassword"));
			return ;
		}
		setError("");
		try
		{
			await register(username, email, password);
			navigate("/login");
		}
		catch (err)
		{
			setError(err.message);
		}
	}
	return (
		<div className='register-page'>
			<h1>Task Manager</h1>
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
							<input id='password' type="password" autoComplete="new-password" aria-describedby="password-help" required value={password} onChange={(e) => setPassword(e.target.value)} />
							<small id='password-help' className='password-help'>{t("register.passwordRules", passwordLimits)}</small>
						</div>
						<div className='input-field'>
							<label htmlFor='confirmpassword'>{t("register.confirmpassword")} : </label>
							<input id='confirmpassword' type="password" autoComplete="new-password" required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
							{confirmPassword && confirmPassword !== password && (
								<small className='password-help password-mismatch' aria-live="polite">{t("register.falsepassword")}</small>
							)}
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