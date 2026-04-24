from statistics import mean


class LocalAlgorithmProvider:
    name = "local"

    def analyze_chart(self, context: dict) -> dict:
        labels = context["x_axis"]
        actual_energy = context["series"]["actual_energy"]
        baseline_energy = context.get("baseline_energy") or actual_energy
        weather = context.get("weather") or []
        calendar = context.get("calendar") or []
        emission_factor_kg = context.get("average_emission_factor_kg_per_kwh", 0.2)

        points = []
        for index, label in enumerate(labels):
            baseline = float(baseline_energy[index]) if index < len(baseline_energy) else 0.0
            weather_item = weather[index] if index < len(weather) else {}
            calendar_item = calendar[index] if index < len(calendar) else {}

            predicted = self._weather_adjusted_prediction(baseline, weather_item, calendar_item)
            optimized = self._conservative_optimization(predicted, weather_item)
            points.append(
                {
                    "x": label,
                    "predicted_energy": round(predicted, 3),
                    "predicted_co2": round(predicted * emission_factor_kg, 3),
                    "optimized_energy": round(optimized, 3),
                    "optimized_co2": round(optimized * emission_factor_kg, 3),
                }
            )

        avg_actual = mean([value for value in actual_energy if value > 0] or [0])
        avg_expected = mean([point["predicted_energy"] for point in points] or [0])
        anomalies = self._anomalies(labels, actual_energy, points)

        return {
            "provider": self.name,
            "points": points,
            "explanations": [
                "Lokaler Standardalgorithmus: Erwartungswerte nutzen Backend-Baseline, Wetter- und Kalenderindikatoren.",
                f"Der mittlere Ist-Verbrauch liegt bei {avg_actual:.1f} kWh, der lokale Erwartungswert bei {avg_expected:.1f} kWh.",
            ],
            "influencing_factors": [
                "kalte Außentemperatur erhöht den erwarteten Heizbedarf",
                "Regen, Schnee oder Frost werden als zusätzliche Heizbedarfsindikatoren berücksichtigt",
                "Wochenenden und Feiertage erhöhen vorsichtig den erwarteten Anwesenheitsanteil",
            ],
            "anomalies": anomalies,
            "fallback_used": False,
        }

    def generate_report(self, context: dict) -> dict:
        summary = context["summary"]
        scope = context["scope"]
        title = f"Energiebericht für {scope['label']}"
        overview = (
            f"Im ausgewählten Zeitraum wurden {summary['total_energy_kwh']:.1f} kWh "
            f"und {summary['total_co2_kg']:.1f} kg CO2 erfasst."
        )
        findings = [
            "Die harten Kennzahlen stammen aus lokaler CSV- und SQLite-Aggregation.",
            "Prognose und Optimierung basieren lokal auf Baseline, Wetter, Feiertagen und Wochenenden.",
        ]
        optimization = [
            "Konservativ geschätzt sind etwa 5 bis 12 Prozent Einsparung realistisch, wenn Ausreißer geprüft werden.",
            "Priorität haben Wohnungen oder Gebäude mit dauerhaftem Verbrauch oberhalb des Erwartungswerts.",
        ]
        plain = " ".join([title, overview, *findings, *optimization])
        return {
            "provider": self.name,
            "title": title,
            "overview": overview,
            "main_findings": findings,
            "influencing_factors": context.get("ai_explanations", {}).get("influencing_factors", []),
            "forecast_notes": ["Die Forecast-Werte stammen vom lokalen Standardalgorithmus."],
            "optimization_notes": optimization,
            "risks_and_uncertainties": [
                "Kurze Datenhistorien reduzieren die Aussagekraft der Prognose.",
                "Ohne Innenraumfeuchte oder Fenstersensorik bleiben Nutzerverhalten und Lüftung nur indirekte Faktoren.",
            ],
            "plain_text_report": plain,
            "fallback_used": False,
        }

    def chat(self, context: dict, message: str) -> dict:
        summary = context.get("summary", {})
        scope = context.get("scope", {"label": "Gesamtbestand"})
        answer = (
            f"Lokaler Fallback: Für '{scope.get('label')}' liegen "
            f"{summary.get('total_energy_kwh', 0):.1f} kWh und "
            f"{summary.get('total_co2_kg', 0):.1f} kg CO2 im Kontext vor. "
            "Für freie Chat-Interpretation sollte Gemini konfiguriert sein."
        )
        return {
            "provider": self.name,
            "answer": answer,
            "referenced_metrics": ["total_energy_kwh", "total_co2_kg", "period", "scope"],
            "caveats": ["Lokaler Chat-Fallback aktiv, weil Gemini nicht verfügbar war."],
            "fallback_used": True,
        }

    @staticmethod
    def _weather_adjusted_prediction(baseline: float, weather_item: dict, calendar_item: dict) -> float:
        factor = 1.0
        temperature = weather_item.get("temperature_c")
        if temperature is not None:
            factor += max(0.0, 15.0 - float(temperature)) * 0.015
            factor -= max(0.0, float(temperature) - 18.0) * 0.01
        if weather_item.get("snow_or_frost"):
            factor += 0.06
        if (weather_item.get("precipitation_mm") or 0) >= 4:
            factor += 0.025
        if calendar_item.get("is_weekend"):
            factor += 0.025
        if calendar_item.get("is_holiday"):
            factor += 0.04
        return max(baseline * factor, 0.0)

    @staticmethod
    def _conservative_optimization(predicted: float, weather_item: dict) -> float:
        saving_factor = 0.9
        if weather_item.get("snow_or_frost"):
            saving_factor = 0.93
        return max(predicted * saving_factor, 0.0)

    @staticmethod
    def _anomalies(labels: list[str], actual_energy: list[float], points: list[dict]) -> list[str]:
        anomalies = []
        for label, actual, point in zip(labels, actual_energy, points):
            expected = point["predicted_energy"]
            if expected > 0 and actual > expected * 1.25:
                anomalies.append(f"{label}: Verbrauch liegt deutlich über dem lokalen Erwartungswert.")
            elif expected > 0 and actual < expected * 0.65:
                anomalies.append(f"{label}: Verbrauch liegt deutlich unter dem lokalen Erwartungswert.")
        return anomalies
