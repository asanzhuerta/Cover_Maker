<script lang="ts">
  import type { Schemas } from "$lib/api/client";
  import ModelList from "$lib/components/ModelList.svelte";
  import { connection } from "$lib/connection.svelte";
  import { t } from "$lib/i18n.svelte";

  let system = $state<Schemas["SystemOut"] | null>(null);

  $effect(() => {
    if (connection.status === "ready" && connection.api && !system) {
      void connection.api
        .GET("/system")
        .then(({ data }) => (system = data ?? null));
    }
  });
</script>

<header class="page-head">
  <div>
    <h1>{t("models.title")}</h1>
    <p>{t("welcome.modelsHint")}</p>
  </div>
</header>
<ModelList recommendedPreset={system?.recommended_preset ?? ""} />
