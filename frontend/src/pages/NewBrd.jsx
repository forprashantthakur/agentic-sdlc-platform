import { useState } from 'react'
import Stepper, { STEPS } from '../components/Stepper'
import BusinessContext from './steps/BusinessContext'
import KnowledgeIngestion from './steps/KnowledgeIngestion'
import Discovery from './steps/Discovery'
import AiAnalysis from './steps/AiAnalysis'
import Review from './steps/Review'
import GenerateBrd from './steps/GenerateBrd'

export default function NewBrd({ project, setProject, run, setRun }) {
  const [step, setStep] = useState('context')
  const [done, setDone] = useState([])

  const advance = (from) => {
    setDone((d) => (d.includes(from) ? d : [...d, from]))
    const i = STEPS.findIndex((s) => s.id === from)
    setStep(STEPS[i + 1]?.id ?? from)
  }
  const back = (from) => {
    const i = STEPS.findIndex((s) => s.id === from)
    setStep(STEPS[i - 1]?.id ?? from)
  }

  return (
    <>
      <Stepper current={step} completed={done} onSelect={setStep} />
      {step === 'context' && <BusinessContext project={project} onCreated={setProject} onNext={() => advance('context')} />}
      {step === 'ingestion' && <KnowledgeIngestion project={project} onNext={() => advance('ingestion')} onBack={() => back('ingestion')} />}
      {step === 'discovery' && <Discovery project={project} onNext={() => advance('discovery')} onBack={() => back('discovery')} />}
      {step === 'analysis' && <AiAnalysis project={project} run={run} setRun={setRun} onNext={() => advance('analysis')} onBack={() => back('analysis')} />}
      {step === 'review' && <Review project={project} onNext={() => advance('review')} onBack={() => back('review')} />}
      {step === 'generate' && <GenerateBrd project={project} onBack={() => back('generate')} />}
    </>
  )
}
