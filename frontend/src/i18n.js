import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import HttpBackend from "i18next-http-backend";

i18n.on("languageChanged", (lng) =>
{
	document.documentElement.lang = lng;
});

i18n
	.use(HttpBackend)
	.use(LanguageDetector)
	.use(initReactI18next)
	.init({
		fallbackLng: "en",
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