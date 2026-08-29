import { useTranslation } from "react-i18next";

function LanguageSwitcher()
{
	const { i18n } = useTranslation();

	function handleChange(langue)
	{
		i18n.changeLanguage(langue.target.value);
	}

	return (
		<select className="language-switcher" value={i18n.language} onChange={handleChange}>
			<option value="fr">🇫🇷 Français</option>
			<option value="en">🇬🇧 English</option>
			<option value="es">🇪🇸 Español</option>
		</select>
	);
}

export default LanguageSwitcher;