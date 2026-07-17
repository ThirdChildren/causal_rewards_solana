import { Nav } from './components/Nav'
import { Hero } from './components/Hero'
import { Stats } from './components/Stats'
import { Problem } from './components/Problem'
import { Approach } from './components/Approach'
import { Workflow } from './components/Workflow'
import { WhySolana } from './components/WhySolana'
import { UseCase } from './components/UseCase'
import { Architecture } from './components/Architecture'
import { Roadmap } from './components/Roadmap'
import { GrantFit } from './components/GrantFit'
import { CtaFooter } from './components/Footer'

export default function App() {
  return (
    <div className="min-h-screen bg-paper">
      <Nav />
      <main>
        <Hero />
        <Stats />
        <Problem />
        <Approach />
        <Workflow />
        <WhySolana />
        <UseCase />
        <Architecture />
        <Roadmap />
        <GrantFit />
      </main>
      <CtaFooter />
    </div>
  )
}
