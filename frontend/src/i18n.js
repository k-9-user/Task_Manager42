import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDectector from "i18next-browser-languagedetector";
import HttpBacken from "i18next-http-backend";

i18n
	.use(HttpBacken)
	.use(LanguageDectector)
	.use(initReactI18next)
	.init({
		fallbacking: "en",
		supportedLngs: ["en", "fr", "es"],
		backend: {
			loadPath: "/locales/{{lng}}/translation.json",
		},
		interpolation:
		{
			escapeValue: false,
		},
	});

	export default i18n;