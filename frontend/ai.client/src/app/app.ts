import { Component, inject, signal } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';
import { Sidenav } from './components/sidenav/sidenav';
import { ErrorToastComponent } from './components/error-toast/error-toast.component';
import { ToastComponent } from './components/toast';
import { SidenavService } from './services/sidenav/sidenav.service';
import { HeaderService } from './services/header/header.service';
import { TooltipDirective } from './components/tooltip/tooltip.directive';

@Component({
  selector: 'app-root',
  imports: [
    RouterOutlet, 
    Sidenav, 
    ErrorToastComponent, 
    ToastComponent, 
    TooltipDirective
  ],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  protected readonly title = signal('boisestate.ai');
  protected sidenavService = inject(SidenavService);
  protected headerService = inject(HeaderService);
  private router = inject(Router);

  newChat() {
    this.router.navigate(['']);
  }
}
