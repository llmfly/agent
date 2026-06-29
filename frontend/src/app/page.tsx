import { GlassHeader } from "@/components/landing/glass-header";
import { HeroSection } from "@/components/landing/hero-section";
import { SiteFooter } from "@/components/landing/site-footer";

export default function LandingPage() {
  return (
    <div className="home-container">
      <GlassHeader />
      <main className="flex w-full flex-col">
        <HeroSection />
      </main>
      <SiteFooter />
    </div>
  );
}
